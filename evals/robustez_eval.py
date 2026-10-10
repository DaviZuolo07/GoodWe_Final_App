"""
Eval de robustez ponta a ponta: perguntas curtas, como o morador digita na interface.

    python -m evals.robustez_eval --modo denso   --k 4     # retriever das iterações 1 e 2
    python -m evals.robustez_eval --modo hibrido --k 6     # configuração da iteração 3

POR QUE EXISTE, ALÉM DO RAGAS: o eval set do RAGAS (`eval_set_rag.json`) tem
perguntas longas e específicas, e as duas iterações chegaram a 100% de resposta
nele. Na interface, "Qual a potência do GW22K-HCA-20" (sem "nominal de saída")
recebeu a recusa. O `recall_retriever --set robustez` mostrou o porquê (o trecho
não chegava ao top-k); este script mede o que o usuário vê: o bot respondeu, e a
resposta está apoiada num trecho que contém o fato?

DUAS MÉTRICAS, AS DUAS DETERMINÍSTICAS (sem juiz LLM):
  - `taxa_resposta`: fração dos casos em que o bot NÃO devolveu recusa nem
    encaminhamento. Todos os casos têm resposta na base.
  - `fato_na_fonte_citada`: a resposta cita (documento, página) de um trecho
    recuperado cujo texto contém a evidência literal do caso, OU a própria
    resposta contém a evidência. É a versão automática de "respondeu certo e
    com a fonte certa". Mais estrita que a taxa de resposta: responder com o
    trecho errado não conta.

A evidência é estrita: "22 kW" do regimento responde a N01 tanto quanto o
"22000" do datasheet, mas só o segundo conta. Por isso a lista de respostas vai
para o JSON, para conferência humana (`--detalhes` imprime todas).

Mesma régua do RAGAS: temperature 0, mesmo modelo do `.env`, mesmo prompt.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from src.chain.rag import ChatbotRAG
from src.guardrails.moderation import normalizar
from src.rag import prompt_rag, retriever

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "evals" / "resultados"


def _contem(texto: str, alvo: str) -> bool:
    return normalizar(alvo) in normalizar(" ".join((texto or "").split()))


def avaliar(modo: str, k: int, versao: str, modelo: str | None, detalhes: bool) -> dict:
    dados = json.loads((RAIZ / "evals" / "eval_set_robustez.json").read_text(encoding="utf-8"))
    rec = retriever.Recuperador(k=k, modo=modo)
    bot = ChatbotRAG(versao_prompt=versao, model=modelo, recuperador=rec)
    linhas = []
    for c in dados["casos"]:
        inicio = time.perf_counter()
        r = bot.responder(c["pergunta"])
        trechos = {(t.documento, t.pagina): t for t in rec.recuperar(c["pergunta"])}
        citadas = prompt_rag.extrair_citacoes(r.texto)
        respondeu = r.rota == "rag"
        fato = respondeu and (_contem(r.texto, c["evidencia"]) or any(
            (d, p) in trechos and _contem(trechos[(d, p)].texto, c["evidencia"]) for d, p in citadas))
        linhas.append({"id": c["id"], "pergunta": c["pergunta"], "rota": r.rota, "respondeu": respondeu,
                       "fato_na_fonte_citada": fato, "resposta": r.texto, "citacoes": r.citacoes,
                       "fontes": [f"{f['documento']} p{f['pagina']} ({f['score']})" for f in r.fontes],
                       "segundos": round(time.perf_counter() - inicio, 1)})
        marca = "OK " if fato else ("RES" if respondeu else "REC")
        print(f"  {marca} {c['id']} {c['pergunta']}")
        if detalhes:
            print(f"        {r.texto}")
    n = len(linhas)
    return {
        "eval_set": f"{dados['meta']['nome']} v{dados['meta']['versao']}",
        "config": bot.descrever(),
        "n": n,
        "taxa_resposta": round(sum(x["respondeu"] for x in linhas) / n, 4),
        "fato_na_fonte_citada": round(sum(x["fato_na_fonte_citada"] for x in linhas) / n, 4),
        "recusados": [x["id"] for x in linhas if not x["respondeu"]],
        "sem_fato": [x["id"] for x in linhas if not x["fato_na_fonte_citada"]],
        "casos": linhas,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Eval de robustez (perguntas de morador) ponta a ponta")
    ap.add_argument("--modo", default=retriever.MODO, choices=list(retriever.MODOS))
    ap.add_argument("--k", type=int, default=retriever.K)
    ap.add_argument("--prompt", default=prompt_rag.VERSAO_PADRAO, choices=list(prompt_rag.VERSOES))
    ap.add_argument("--modelo", default=None, help="padrão: OLLAMA_MODEL do .env")
    ap.add_argument("--rotulo", default=None, help="sufixo do arquivo de saída")
    ap.add_argument("--detalhes", action="store_true", help="imprime cada resposta")
    a = ap.parse_args()

    print(f"robustez: busca {a.modo}, k {a.k}, prompt {a.prompt}")
    saida = avaliar(a.modo, a.k, a.prompt, a.modelo, a.detalhes)
    print(f"\ntaxa de resposta       {saida['taxa_resposta']:.3f}   recusados: {saida['recusados']}")
    print(f"fato na fonte citada   {saida['fato_na_fonte_citada']:.3f}   sem fato:  {saida['sem_fato']}")
    PASTA.mkdir(parents=True, exist_ok=True)
    rotulo = a.rotulo or f"{a.modo}_k{a.k}"
    destino = PASTA / f"robustez_{rotulo}_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.write_text(json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"gravado em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
