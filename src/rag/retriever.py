"""
Retriever (Aula 05/06): top-k por similaridade de cosseno, com limiar.

O LIMIAR NÃO DECIDE SOZINHO SE A BASE TEM A RESPOSTA — e isto foi medido.
Calibração de 09/10/2026 (117 chunks, 3 PDFs GoodWe, sumário excluído,
score = 1 − distância de cosseno do melhor chunk):

    perguntas respondíveis pela base (12)          0,704 – 0,846
    fora do domínio (bolo, Copa, imposto de renda)  0,624 – 0,733
    do domínio mas fora da base (Lei 18.403, tarifa
    Enel, regimento, "Tesla Wallbox")               0,683 – 0,820

As faixas se sobrepõem: similaridade mede ASSUNTO, não se o trecho contém a
resposta. "Potência do Tesla Wallbox" casa com a tabela de potências do HCA G2
melhor que muita pergunta legítima. Um limiar alto o bastante para recusar
isso recusaria perguntas boas.

Por isso a recusa tem duas camadas:
  1. aqui, um limiar BAIXO (0,65) que só corta o claramente fora de assunto —
     sem chunk, nem se chama o LLM, e o `scope_validator` decide a recusa;
  2. no prompt RAG, o modelo devolve a recusa literal quando os trechos
     recuperados não contêm a resposta.

`K = 4`: com chunks de ~1000 caracteres são ~1000 tokens de contexto, e a
resposta certa apareceu entre os 3 primeiros em todas as perguntas da
calibração. `k` é um dos parâmetros comparados no bloco C.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.rag import vector_store

K = 4
LIMIAR = 0.65

TAMANHO_TRECHO = 240   # quanto do chunk aparece no painel de fontes


@dataclass(frozen=True)
class Trecho:
    documento: str
    pagina: int
    score: float
    texto: str
    chunk_id: str
    categoria: str

    @property
    def citacao(self) -> str:
        return f"(fonte: {self.documento}, página {self.pagina})"

    def resumo(self) -> dict:
        texto = " ".join(self.texto.split())
        return {"documento": self.documento, "pagina": self.pagina, "score": round(self.score, 3),
                "trecho": texto[:TAMANHO_TRECHO] + ("…" if len(texto) > TAMANHO_TRECHO else ""),
                "chunk_id": self.chunk_id}


def para_trecho(doc: Document, score: float) -> Trecho:
    m = doc.metadata
    return Trecho(documento=m["documento"], pagina=int(m["pagina"]), score=float(score),
                  texto=doc.page_content, chunk_id=m.get("chunk_id", ""),
                  categoria=m.get("categoria", ""))


class Recuperador:
    """Busca na coleção e devolve só o que passa do limiar, do mais ao menos similar."""

    def __init__(self, store: Chroma | None = None, k: int = K, limiar: float = LIMIAR):
        self.store = store or vector_store.abrir()
        self.k = k
        self.limiar = limiar

    def buscar_tudo(self, pergunta: str) -> list[Trecho]:
        """Top-k sem filtro — para depuração e para o eval registrar o que foi descartado."""
        pares = self.store.similarity_search_with_relevance_scores(pergunta, k=self.k)
        return [para_trecho(doc, score) for doc, score in pares]

    def recuperar(self, pergunta: str) -> list[Trecho]:
        return [t for t in self.buscar_tudo(pergunta) if t.score >= self.limiar]

    def descrever(self) -> dict:
        return {"k": self.k, "limiar": self.limiar, "metrica": vector_store.METRICA,
                "colecao": vector_store.NOME_COLECAO}
