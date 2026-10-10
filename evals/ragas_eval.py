"""
Avaliação do RAG (Aula 07): RAGAS (faithfulness, answer_relevancy) + rubrica manual.

    python -m evals.ragas_eval --iteracao 1                      # config padrão (prompt v1, chunk 1000/150, k 4)
    python -m evals.ragas_eval --iteracao 2 --prompt v2 --k 6
    python -m evals.ragas_eval --iteracao chunk512 --chunk 512   # experimento de chunk_size
    python -m evals.ragas_eval --iteracao modeloB --modelo gemma4:31b

Grava `evals/resultados/ragas_<iteracao>_<carimbo>.json` com os scores E todos
os parâmetros (chunk_size, chunk_overlap, k, limiar, temperature, top_p,
max_tokens, seed, modelo, juiz, versão do prompt, eval set). Número sem
parâmetro não é reproduzível e não entra no relatório.

MESMA RÉGUA (invariante 6): eval set congelado (`eval_set_rag.json`), juiz fixo
(`MODELO_JUIZ`, temperature 0, seed 42), embeddings fixos (nomic-embed-text),
mesmo tokenizador. O que muda entre iterações é só o que está sendo testado.

O QUE CADA MÉTRICA PEGA:
  faithfulness       (RAGAS) as afirmações da resposta estão nos trechos? -> alucinação
  answer_relevancy   (RAGAS) a resposta responde à pergunta? -> recusa indevida, desvio
  fidelidade/relevancia_manual  a mesma pergunta, rubrica 0–1 da Aula 07 (fallback)
  determinísticas    citou fonte? citou o documento certo? recusou quando devia?

Casos de RECUSA (`deve_recusar`) não entram no RAGAS — resposta certa é "não
encontrei" e faithfulness de uma recusa não tem afirmação para checar. Eles são
medidos pela checagem determinística `recusa_correta`.

Faithfulness de uma recusa INDEVIDA (o caso tinha resposta e o bot recusou)
sai NaN no RAGAS (zero afirmações). Por isso o relatório traz junto a
`taxa_resposta` e o answer_relevancy, que pune a recusa com 0: média de
faithfulness alta com taxa de resposta baixa é um bot que acerta calando.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.chain.llm import PERFIS, get_llm
from src.chain.rag import PERFIL_LLM, ChatbotRAG
from src.rag import chunking, embeddings, loader, prompt_rag, retriever, vector_store

load_dotenv()

RAIZ = Path(__file__).resolve().parents[1]
EVAL_SET = RAIZ / "evals" / "eval_set_rag.json"
PASTA_RESULTADOS = RAIZ / "evals" / "resultados"
SEED = 42


def _juiz_padrao() -> str:
    return (os.getenv("MODELO_JUIZ") or "gpt-oss:120b").strip()


def carregar_casos(limite: int | None = None) -> tuple[dict, list[dict]]:
    dados = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    casos = [c for c in dados["casos"] if not c.get("invalidado")]
    return dados["meta"], casos[:limite] if limite else casos


def abrir_store(chunk: int, overlap: int, estrategia: str):
    """Coleção padrão para a config padrão; coleção própria em chroma_db/_eval/ para as outras."""
    if (chunk, overlap, estrategia) == (chunking.TAMANHO, chunking.SOBREPOSICAO, chunking.ESTRATEGIA):
        store = vector_store.abrir()
        if store._collection.count():
            return store, store._collection.count()
    destino = vector_store.pasta_chroma() / "_eval" / f"c{chunk}_o{overlap}_{estrategia}"
    chunks = chunking.dividir(loader.carregar_base(), tamanho=chunk, sobreposicao=overlap,
                              estrategia=estrategia)
    return vector_store.indexar(chunks, persist_directory=destino), len(chunks)


def _media(valores: list[float]) -> float | None:
    ok = [v for v in valores if v is not None and not (isinstance(v, float) and math.isnan(v)) and v >= 0]
    return round(sum(ok) / len(ok), 4) if ok else None


def rodar_ragas(amostras: list[dict], juiz: str) -> list[dict]:
    """faithfulness e answer_relevancy por amostra, com o juiz e os embeddings fixos."""
    from datasets import Dataset
    from ragas import RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, faithfulness

    ragas_llm = LangchainLLMWrapper(get_llm("classificador", model=juiz, num_predict=4096))
    ragas_embs = LangchainEmbeddingsWrapper(embeddings.get_embeddings())
    faithfulness.llm = ragas_llm
    answer_relevancy.llm = ragas_llm
    answer_relevancy.embeddings = ragas_embs

    ds = Dataset.from_dict({
        "question": [a["pergunta"] for a in amostras],
        "answer": [a["resposta"] for a in amostras],
        "contexts": [a["contextos"] or ["(nenhum trecho recuperado)"] for a in amostras],
    })
    res = evaluate(ds, metrics=[faithfulness, answer_relevancy],
                   run_config=RunConfig(timeout=300, max_retries=3, max_workers=4, seed=SEED),
                   show_progress=True, raise_exceptions=False)
    df = res.to_pandas()
    return [{"faithfulness": None if math.isnan(f) else round(float(f), 4),
             "answer_relevancy": None if math.isnan(r) else round(float(r), 4)}
            for f, r in zip(df["faithfulness"], df["answer_relevancy"])]


def avaliar(iteracao: str, versao: str, chunk: int, overlap: int, estrategia: str, k: int, limiar: float,
            modelo: str | None, juiz: str, usar_ragas: bool, usar_manual: bool,
            limite: int | None) -> dict:
    meta, casos = carregar_casos(limite)
    store, n_chunks = abrir_store(chunk, overlap, estrategia)
    bot = ChatbotRAG(versao_prompt=versao, model=modelo,
                     recuperador=retriever.Recuperador(store=store, k=k, limiar=limiar))

    linhas = []
    for c in casos:
        t0 = time.perf_counter()
        r = bot.responder(c["pergunta"])
        latencia = round(time.perf_counter() - t0, 2)
        # O contexto avaliado leva o mesmo rótulo [documento, página] que o modelo recebeu
        # no prompt. Sem ele, o RAGAS lê a citação "(fonte: X, página 2)" como afirmação
        # sem suporte e pune a resposta certa (régua 0, ver docs/CHANGELOG_SPRINT4.md).
        contextos = [f"[{t.documento}, página {t.pagina}]\n{t.texto}"
                     for t in bot._etapa_busca({"pergunta": c["pergunta"]})["usados"]]
        docs_citados = sorted({cit.split("fonte:")[1].split(",")[0].strip() for cit in r.citacoes})
        recusou = r.rota in ("sem_contexto", "recusa_llm", "recusa_escopo", "bloqueio_moderacao")
        linhas.append({
            "id": c["id"], "categoria": c["categoria"], "pergunta": c["pergunta"],
            "deve_recusar": c["deve_recusar"], "fontes_aceitas": c["fontes_aceitas"],
            "resposta_referencia": c["resposta_referencia"],
            "resposta": r.texto, "rota": r.rota, "contextos": contextos,
            "fontes": r.fontes, "descartados": r.descartados, "citacoes": r.citacoes,
            "citacao_adicionada": r.citacao_adicionada, "citacoes_invalidas": r.citacoes_invalidas,
            "recusou": recusou, "citou_fonte": bool(r.citacoes),
            "fonte_correta": bool(set(c["fontes_aceitas"]) & set(docs_citados)) if c["fontes_aceitas"] else None,
            "recusa_correta": recusou if c["deve_recusar"] else None,
            "latencia_s": latencia, "tokens_entrada": r.tokens_servidor_entrada,
            "tokens_saida": r.tokens_servidor_saida,
        })
        print(f"  [{c['id']}] {r.rota:13s} {latencia:5.1f}s  {r.texto[:90]!r}")

    respondiveis = [l for l in linhas if not l["deve_recusar"]]

    if usar_manual:
        from evals.juiz_rag import JuizRAG
        juiz_manual = JuizRAG(juiz)
        for l in respondiveis:
            l["fidelidade_manual"] = juiz_manual.fidelidade(l["resposta"], l["contextos"]) \
                if not l["recusou"] else None
            l["relevancia_manual"] = juiz_manual.relevancia(l["pergunta"], l["resposta"])
        print("  rubrica manual: ok")

    erro_ragas = None
    if usar_ragas:
        try:
            amostras = [{"pergunta": l["pergunta"], "resposta": l["resposta"], "contextos": l["contextos"]}
                        for l in respondiveis]
            for l, s in zip(respondiveis, rodar_ragas(amostras, juiz)):
                l.update(s)
            print("  RAGAS: ok")
        except Exception as e:   # o fallback manual já tem o número
            erro_ragas = f"{type(e).__name__}: {str(e)[:300]}"
            print(f"  RAGAS falhou: {erro_ragas}")

    recusas = [l for l in linhas if l["deve_recusar"]]
    resumo = {
        "casos": len(linhas), "respondiveis": len(respondiveis), "recusas": len(recusas),
        "faithfulness": _media([l.get("faithfulness") for l in respondiveis]),
        "faithfulness_n": sum(1 for l in respondiveis if l.get("faithfulness") is not None),
        "answer_relevancy": _media([l.get("answer_relevancy") for l in respondiveis]),
        "fidelidade_manual": _media([l.get("fidelidade_manual") for l in respondiveis]),
        "relevancia_manual": _media([l.get("relevancia_manual") for l in respondiveis]),
        "taxa_resposta": round(sum(not l["recusou"] for l in respondiveis) / len(respondiveis), 4),
        "taxa_citacao": round(sum(l["citou_fonte"] for l in respondiveis if not l["recusou"])
                              / max(1, sum(not l["recusou"] for l in respondiveis)), 4),
        "taxa_fonte_correta": round(sum(bool(l["fonte_correta"]) for l in respondiveis) / len(respondiveis), 4),
        "recusa_correta": f"{sum(l['recusa_correta'] for l in recusas)}/{len(recusas)}",
        "citacoes_invalidas": sum(len(l["citacoes_invalidas"]) for l in linhas),
        "latencia_media_s": round(sum(l["latencia_s"] for l in linhas) / len(linhas), 2),
        "tokens_entrada_medio": round(sum(l["tokens_entrada"] for l in linhas) / len(linhas)),
        "tokens_saida_medio": round(sum(l["tokens_saida"] for l in linhas) / len(linhas)),
    }
    perfil = PERFIS[PERFIL_LLM]
    parametros = {
        "iteracao": iteracao, "prompt_rag": versao, "eval_set": f"{meta['nome']} v{meta['versao']}",
        "chunk_size": chunk, "chunk_overlap": overlap, "separadores": estrategia,
        "chunks_indexados": n_chunks,
        "k": k, "limiar": limiar, "temperature": perfil["temperature"], "top_p": perfil["top_p"],
        "max_tokens": perfil["num_predict"], "seed": perfil["seed"],
        "modelo": bot.descrever()["llm"]["model"], "juiz": juiz,
        "embeddings": embeddings.nome_do_modelo(), "regua": "contexto rotulado com [documento, página]", "metricas_ragas": usar_ragas and not erro_ragas,
        "erro_ragas": erro_ragas,
        "sistema": {**bot.descrever(), "chunking": chunking.descrever(chunk, overlap, estrategia)},
    }
    return {"parametros": parametros, "resumo": resumo, "casos": linhas}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="RAGAS + rubrica manual sobre evals/eval_set_rag.json")
    ap.add_argument("--iteracao", required=True, help="rótulo: 1, 2, chunk512, modeloB...")
    ap.add_argument("--prompt", default=prompt_rag.VERSAO_PADRAO, choices=list(prompt_rag.VERSOES))
    ap.add_argument("--chunk", type=int, default=chunking.TAMANHO)
    ap.add_argument("--overlap", type=int, default=None, help="padrão: 150 para 1000, senão chunk//8")
    ap.add_argument("--separadores", default=chunking.ESTRATEGIA, choices=list(chunking.ESTRATEGIAS))
    ap.add_argument("--k", type=int, default=retriever.K)
    ap.add_argument("--limiar", type=float, default=retriever.LIMIAR)
    ap.add_argument("--modelo", default=None, help="padrão: OLLAMA_MODEL do .env")
    ap.add_argument("--juiz", default=_juiz_padrao())
    ap.add_argument("--sem-ragas", action="store_true")
    ap.add_argument("--sem-manual", action="store_true")
    ap.add_argument("--limite", type=int, default=None, help="só os N primeiros casos (depuração)")
    a = ap.parse_args()
    overlap = a.overlap if a.overlap is not None else (
        chunking.SOBREPOSICAO if a.chunk == chunking.TAMANHO else a.chunk // 8)

    print(f"iteração {a.iteracao}: prompt {a.prompt}, chunk {a.chunk}/{overlap} ({a.separadores}), k {a.k}, "
          f"limiar {a.limiar}, juiz {a.juiz}")
    inicio = time.perf_counter()
    saida = avaliar(a.iteracao, a.prompt, a.chunk, overlap, a.separadores, a.k, a.limiar, a.modelo, a.juiz,
                    not a.sem_ragas, not a.sem_manual, a.limite)
    saida["parametros"]["duracao_s"] = round(time.perf_counter() - inicio, 1)

    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_RESULTADOS / f"ragas_{a.iteracao}_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.write_text(json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + json.dumps(saida["resumo"], indent=2, ensure_ascii=False))
    print(f"\ngravado em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
