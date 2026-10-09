"""
Embeddings (Aula 05): `nomic-embed-text`, 768 dimensões, no Ollama LOCAL.

POR QUE LOCAL e não o Ollama Cloud que serve os modelos de chat:
em 09/10/2026 o `nomic-embed-text` não aparece entre os modelos da conta, e
`POST https://ollama.com/api/embed` responde 401 para QUALQUER modelo de
embedding com a mesma chave que o `/api/chat` aceita. O modelo pedido pelo §3
é o mesmo; muda só o host (`OLLAMA_HOST_LOCAL`). Pré-requisito:

    ollama pull nomic-embed-text

Efeito colateral bom: indexar e buscar não gasta cota da nuvem e não depende
dela — se a nuvem cair, a busca continua funcionando.

POR QUE OS PREFIXOS `search_document:` / `search_query:`:
o nomic-embed-text foi treinado com prefixo de tarefa e o model card manda
usá-los. Sem eles, pergunta e trecho caem em regiões diferentes do espaço e a
similaridade fica achatada (tudo parecido com tudo), o que estraga o limiar de
recusa do retriever. O prefixo é aplicado aqui, uma vez, para que indexação e
busca nunca saiam de sincronia.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings

load_dotenv()

MODELO_PADRAO = "nomic-embed-text"
DIMENSOES = 768
PREFIXO_DOCUMENTO = "search_document: "
PREFIXO_CONSULTA = "search_query: "


def _limpo(nome_var: str, padrao: str) -> str:
    return (os.getenv(nome_var) or padrao).strip().strip('"').strip("'")


def nome_do_modelo() -> str:
    return _limpo("EMBEDDING_MODEL", MODELO_PADRAO)


def host() -> str:
    return _limpo("OLLAMA_HOST_LOCAL", "http://127.0.0.1:11434").rstrip("/")


class EmbeddingsNomic(OllamaEmbeddings):
    """`OllamaEmbeddings` com os prefixos de tarefa do nomic-embed-text."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return super().embed_documents([PREFIXO_DOCUMENTO + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(PREFIXO_CONSULTA + text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await super().aembed_documents([PREFIXO_DOCUMENTO + t for t in texts])

    async def aembed_query(self, text: str) -> list[float]:
        return await super().aembed_query(PREFIXO_CONSULTA + text)


def get_embeddings() -> OllamaEmbeddings:
    modelo = nome_do_modelo()
    classe = EmbeddingsNomic if modelo.startswith("nomic-embed-text") else OllamaEmbeddings
    # validate_model_on_init=False: a fábrica não pode fazer rede no import.
    return classe(model=modelo, base_url=host(), validate_model_on_init=False)


def descrever() -> dict:
    modelo = nome_do_modelo()
    return {"modelo": modelo, "host": host(), "provedor": "local",
            "dimensoes": DIMENSOES if modelo.startswith("nomic-embed-text") else None,
            "prefixos": modelo.startswith("nomic-embed-text")}
