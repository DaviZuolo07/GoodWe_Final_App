"""
Vector store persistente (Aula 05): ChromaDB em `chroma_db/` na raiz.

    python -m src.rag.vector_store              # estado da coleção
    python -m src.rag.vector_store --reindexar  # recarrega data/knowledge_base/ do zero

Divergência deliberada das aulas: `langchain_chroma.Chroma` (pacote dedicado,
é o pin do projeto) no lugar de `langchain_community.vectorstores.Chroma`. A API
usada aqui (`add_documents`, `similarity_search_with_relevance_scores`,
`as_retriever`) é a mesma.

POR QUE COSSENO (`hnsw:space = cosine`): o padrão do Chroma é L2, cuja
distância não tem teto e muda de escala com o modelo de embedding. Com cosseno
o score de relevância fica em [0, 1] (1 − distância) e o limiar de recusa do
retriever é um número interpretável e estável entre reindexações.

POR QUE `--reindexar` APAGA A COLEÇÃO: reindexar é "a coleção passa a ser
exatamente o conteúdo da pasta". Sem apagar, um PDF removido ou renomeado
continuaria respondendo perguntas com citação para um arquivo que não existe.
O `chroma_db/` é gitignored e regenerável a qualquer momento.
"""

from __future__ import annotations

import argparse
import os
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.rag import chunking, embeddings, loader

load_dotenv()

RAIZ = Path(__file__).resolve().parents[2]
NOME_COLECAO = "goodwe_kb"
METRICA = "cosine"


def pasta_chroma() -> Path:
    bruto = (os.getenv("CHROMA_DIR") or "chroma_db").strip().strip('"').strip("'")
    caminho = Path(bruto)
    return caminho if caminho.is_absolute() else RAIZ / caminho


def abrir(persist_directory: Path | None = None, embedding=None) -> Chroma:
    """Abre (ou cria vazia) a coleção persistente. Não indexa nada."""
    return Chroma(
        collection_name=NOME_COLECAO,
        embedding_function=embedding or embeddings.get_embeddings(),
        persist_directory=str(persist_directory or pasta_chroma()),
        collection_metadata={"hnsw:space": METRICA},
    )


def indexar(chunks: list[Document], persist_directory: Path | None = None, embedding=None,
            lote: int = 64) -> Chroma:
    """Apaga a coleção e grava os chunks com os IDs determinísticos do chunking."""
    store = abrir(persist_directory, embedding)
    store.delete_collection()
    store = abrir(persist_directory, embedding)
    for i in range(0, len(chunks), lote):
        parte = chunks[i:i + lote]
        store.add_documents(parte, ids=[c.metadata["chunk_id"] for c in parte])
    return store


def reindexar(pasta_base: Path = loader.PASTA_BASE, persist_directory: Path | None = None,
              embedding=None) -> tuple[Chroma, list[Document]]:
    paginas = loader.carregar_base(pasta_base)
    chunks = chunking.dividir(paginas)
    return indexar(chunks, persist_directory, embedding), chunks


def estatisticas(store: Chroma) -> dict:
    dados = store.get(include=["metadatas"])
    metas = dados["metadatas"]
    return {
        "colecao": NOME_COLECAO,
        "diretorio": str(pasta_chroma()),
        "metrica": METRICA,
        "chunks": len(metas),
        "por_documento": dict(sorted(Counter(m["documento"] for m in metas).items())),
        "por_categoria": dict(sorted(Counter(m["categoria"] for m in metas).items())),
    }


def main():
    ap = argparse.ArgumentParser(description="Índice ChromaDB da base de conhecimento")
    ap.add_argument("--reindexar", action="store_true", help="apaga a coleção e indexa a pasta de novo")
    a = ap.parse_args()

    print(f"embeddings: {embeddings.descrever()}")
    print(f"chunking:   {chunking.descrever()}")
    if a.reindexar:
        inicio = time.perf_counter()
        store, chunks = reindexar()
        print(f"\nindexados {len(chunks)} chunks em {time.perf_counter() - inicio:.1f}s")
    else:
        store = abrir()

    est = estatisticas(store)
    print(f"\ncoleção '{est['colecao']}' em {est['diretorio']} (métrica {est['metrica']})")
    print(f"  chunks: {est['chunks']}")
    for doc, n in est["por_documento"].items():
        print(f"    {n:4d}  {doc}")
    print(f"  categorias: {est['por_categoria']}")
    if not est["chunks"]:
        print("\ncoleção vazia — rode com --reindexar")


if __name__ == "__main__":
    main()
