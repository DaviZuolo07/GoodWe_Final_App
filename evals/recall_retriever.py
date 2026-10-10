"""
Diagnóstico de recuperação, sem LLM: o trecho com a resposta chega ao top-k?

    python -m evals.recall_retriever                         # grade chunk_size x k padrão
    python -m evals.recall_retriever --configs 1000:4,1000:8,512:8
    python -m evals.recall_retriever --set robustez --configs 1000:4 --estrategias estrutura

POR QUE EXISTE: o RAGAS mede a resposta final, que mistura dois erros — o
retriever não trouxe o trecho, ou trouxe e o modelo não usou. Na iteração 1 os
dois apareceram juntos (R01 recusado, R02 respondido com o artigo vizinho). Este
script isola o primeiro: para cada caso respondível do eval set, procura a
"evidência" (um trecho literal da resposta no documento) nos chunks recuperados.
Só usa embeddings locais — roda em segundos e não gasta cota da nuvem, então dá
para varrer a grade antes de gastar uma iteração do RAGAS.

A evidência de cada caso é um texto curto copiado do PDF (não da resposta de
referência), comparado sem acento e sem espaço extra.

`--modos denso,hibrido` mede as duas buscas do `retriever.py` na mesma grade.
`--set robustez` usa `evals/eval_set_robustez.json`: perguntas curtas, como o
morador digita na interface, com a evidência no próprio arquivo. Foi esse conjunto
que mostrou o buraco do denso puro que o eval set do RAGAS (perguntas longas e
específicas) não mostrava.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from src.guardrails.moderation import normalizar
from src.rag import chunking, loader, retriever, vector_store

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "evals" / "resultados"

# Texto literal do documento que responde a cada caso.
EVIDENCIA = {
    "M01": "22000", "M02": "ip66", "M03": "corrente nominal de entrada", "M04": "uma vez a cada 6 meses",
    "M05": "9600", "F01": "azul", "F02": "2 segundos", "F03": "1/3", "F04": "estender o cabo",
    "R01": "4 (quatro) horas", "R02": "15 (quinze) minutos", "R03": "6 (seis) pontos",
    "T01": "2,10 por kwh", "T02": "63,00",
}


def _store(chunk: int, overlap: int, estrategia: str):
    destino = vector_store.pasta_chroma() / "_eval" / f"c{chunk}_o{overlap}_{estrategia}"
    store = vector_store.abrir(persist_directory=destino)
    if not store._collection.count():
        chunks = chunking.dividir(loader.carregar_base(), tamanho=chunk, sobreposicao=overlap,
                                  estrategia=estrategia)
        store = vector_store.indexar(chunks, persist_directory=destino)
    return store


def medir(chunk: int, k: int, casos: list[dict], estrategia: str, modo: str = "denso") -> dict:
    overlap = chunking.SOBREPOSICAO if chunk == chunking.TAMANHO else chunk // 8
    rec = retriever.Recuperador(store=_store(chunk, overlap, estrategia), k=k, modo=modo)
    achou, posicoes = {}, {}
    for c in casos:
        trechos = rec.recuperar(c["pergunta"])
        alvo = normalizar(c.get("evidencia") or EVIDENCIA[c["id"]])
        pos = next((i for i, t in enumerate(trechos, 1) if alvo in normalizar(" ".join(t.texto.split()))), None)
        achou[c["id"]], posicoes[c["id"]] = pos is not None, pos
    return {"chunk_size": chunk, "chunk_overlap": overlap, "separadores": estrategia, "k": k, "modo": modo,
            "recall": round(sum(achou.values()) / len(achou), 4),
            "faltou": [i for i, ok in achou.items() if not ok], "posicao": posicoes}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="256:4,512:4,1000:4,512:8,1000:8",
                    help="chunk:k separados por vírgula; cada um roda com cada estratégia e modo")
    ap.add_argument("--set", default="rag", choices=["rag", "robustez"], help="eval set de perguntas")
    ap.add_argument("--modos", default="denso,hibrido", help="buscas do retriever.py a medir")
    ap.add_argument("--estrategias", default=",".join(chunking.ESTRATEGIAS))
    a = ap.parse_args()
    dados = json.loads((RAIZ / "evals" / f"eval_set_{a.set}.json").read_text(encoding="utf-8"))
    casos = [c for c in dados["casos"] if not c.get("deve_recusar") and not c.get("invalidado")]
    linhas = []
    for estrategia in a.estrategias.split(","):
        for cfg in a.configs.split(","):
            chunk, k = (int(x) for x in cfg.split(":"))
            for modo in a.modos.split(","):
                r = medir(chunk, k, casos, estrategia, modo)
                linhas.append({"set": a.set, **r})
                print(f"{a.set:8s} {estrategia:9s} chunk {chunk:4d}/{r['chunk_overlap']:3d}  k={k}  "
                      f"{modo:7s}  recall={r['recall']:.3f}  faltou={r['faltou']}")
    PASTA.mkdir(parents=True, exist_ok=True)
    destino = PASTA / f"recall_{a.set}_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.write_text(json.dumps(linhas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ngravado em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
