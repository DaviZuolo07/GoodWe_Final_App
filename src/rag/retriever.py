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

`K = 6` desde a iteração 3 (era 4 nas iterações 1 e 2): com 4, a resposta certa
apareceu entre os 3 primeiros em todas as perguntas da calibração e do eval set,
mas em perguntas curtas de morador ela cai entre o 5º e o 6º lugar (a tabela
técnica compete com desenhos que repetem o código do modelo). Medido no eval de
robustez: híbrida k=4 responde 0,875 e k=6 responde 0,917. Custo: ~1/2 a mais de
tokens de contexto por pergunta. `k` é um dos parâmetros comparados no bloco C.

POR QUE A BUSCA É HÍBRIDA (denso + lexical), desde 10/10/2026:
o eval set do RAGAS tem perguntas longas e específicas ("potência nominal de
saída do GW22K-HCA-20") e passava com recall 1,000 só com o denso. Na interface,
o morador pergunta curto, "Qual a potência do GW22K-HCA-20", e o datasheet caiu
para o 5º lugar, atrás de quatro páginas de DESENHO de dimensão que repetem o
código do modelo. Sem a tabela no top-4, o modelo recusou, corretamente, com os
trechos errados. "Qual o peso do carregador?" e "grau de proteção" nem
apareciam no top-12: a tabela técnica tem 40 campos num chunk só, e o embedding
dela é a média de todos, então não "fala" de peso. Medido com
`python -m evals.recall_retriever --set robustez` (perguntas de morador,
`evals/eval_set_robustez.json`); números no docs/CHANGELOG_SPRINT4.md, Fase 7.

O lexical (BM25 sobre os mesmos chunks do Chroma) acha a palavra rara ("peso",
"grau", "gw11k", "baud") que o denso dilui; o denso acha a paráfrase que não
tem palavra em comum. As duas listas são fundidas por Reciprocal Rank Fusion
(RRF, k=60): só a POSIÇÃO entra, então não é preciso calibrar BM25 contra
cosseno. Não é reranking (nenhum modelo reordena nada) e não traz dependência
nova: o BM25 é a classe `IndiceBM25` abaixo.

O LIMIAR CONTINUA SENDO O DO DENSO. A fusão decide a ORDEM; quem decide se um
trecho é relevante o bastante para ir ao modelo continua sendo o cosseno, com o
mesmo 0,65 calibrado acima. Assim, uma pergunta fora de assunto que por acaso
repete uma palavra da base não ganha contexto só pelo BM25, e a recusa se
comporta como antes.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.guardrails.moderation import normalizar
from src.rag import vector_store

K = 6
LIMIAR = 0.65

# "denso" é o retriever das iterações 1 e 2 (medido); "hibrido" é o padrão a
# partir da iteração 3. O eval aceita os dois, para a comparação usar a mesma régua.
MODOS = ("denso", "hibrido")
MODO = "hibrido"
RRF_K = 60                    # constante do artigo original do RRF (Cormack et al., 2009)
BM25_K1, BM25_B = 1.5, 0.75   # valores padrão do Okapi BM25

TAMANHO_TRECHO = 240   # quanto do chunk aparece no painel de fontes

# Palavras que aparecem em quase toda pergunta e não distinguem trecho nenhum.
_STOPWORDS = frozenset("""
a o as os um uma uns umas de do da dos das no na nos nas em por para pra com sem
e ou que qual quais quanto quantos quantas como onde quando porque se
eu meu minha meus minhas voce seu sua tem ter ha esta estao esse essa isso este
isto ao aos pelo pela pelos pelas mais menos muito ja nao sim sobre e agora
""".split())
_TOKEN = re.compile(r"[a-z0-9]+")


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
                "chunk_id": self.chunk_id, "categoria": self.categoria}


def para_trecho(doc: Document, score: float) -> Trecho:
    m = doc.metadata
    return Trecho(documento=m["documento"], pagina=int(m["pagina"]), score=float(score),
                  texto=doc.page_content, chunk_id=m.get("chunk_id", ""),
                  categoria=m.get("categoria", ""))


def tokens(texto: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalizar(texto)) if t not in _STOPWORDS]


class IndiceBM25:
    """BM25 (Okapi) em memória sobre os chunks da coleção, construído uma vez, na 1ª busca."""

    def __init__(self, ids: list[str], textos: list[str]):
        self.ids = ids
        self.freqs = [Counter(tokens(t)) for t in textos]
        self.tamanhos = [sum(f.values()) for f in self.freqs]
        self.media = (sum(self.tamanhos) / len(self.tamanhos)) if self.tamanhos else 0.0
        df = Counter(termo for f in self.freqs for termo in f)
        n = len(ids)
        self.idf = {termo: math.log(1 + (n - d + 0.5) / (d + 0.5)) for termo, d in df.items()}

    def ranking(self, pergunta: str) -> list[str]:
        """IDs com score > 0, do maior para o menor."""
        termos = [t for t in set(tokens(pergunta)) if t in self.idf]
        pontos = []
        for i, f in enumerate(self.freqs):
            norm = BM25_K1 * (1 - BM25_B + BM25_B * self.tamanhos[i] / (self.media or 1))
            s = sum(self.idf[t] * f[t] * (BM25_K1 + 1) / (f[t] + norm) for t in termos if t in f)
            if s > 0:
                pontos.append((s, i))
        return [self.ids[i] for _, i in sorted(pontos, key=lambda p: (-p[0], p[1]))]


def fundir_rrf(*rankings: list[str], k: int = RRF_K) -> list[str]:
    """Reciprocal Rank Fusion: soma 1/(k + posição) de cada lista; empate fica com a ordem da 1ª."""
    pontos: dict[str, float] = {}
    for ranking in rankings:
        for pos, i in enumerate(ranking, start=1):
            pontos[i] = pontos.get(i, 0.0) + 1.0 / (k + pos)
    ordem = {i: n for n, i in enumerate(rankings[0])} if rankings else {}
    return sorted(pontos, key=lambda i: (-pontos[i], ordem.get(i, len(ordem))))


class Recuperador:
    """Busca na coleção e devolve só o que passa do limiar, na ordem da fusão (ou do denso)."""

    def __init__(self, store: Chroma | None = None, k: int = K, limiar: float = LIMIAR,
                 modo: str = MODO):
        if modo not in MODOS:
            raise ValueError(f"modo de busca desconhecido: {modo!r}. Use um de {MODOS}")
        self.store = store or vector_store.abrir()
        self.k = k
        self.limiar = limiar
        self.modo = modo
        self._bm25: IndiceBM25 | None = None
        self._total = 0

    def _indice(self) -> IndiceBM25:
        if self._bm25 is None:
            dados = self.store.get(include=["documents"])
            self._bm25 = IndiceBM25(dados["ids"], dados["documents"])
            self._total = len(dados["ids"])
        return self._bm25

    def buscar_tudo(self, pergunta: str) -> list[Trecho]:
        """Top-k sem filtro — para depuração e para o eval registrar o que foi descartado."""
        if self.modo == "denso":
            pares = self.store.similarity_search_with_relevance_scores(pergunta, k=self.k)
            return [para_trecho(doc, score) for doc, score in pares]
        indice = self._indice()
        # O denso ranqueia a coleção inteira (141 chunks, custo desprezível) para que todo
        # trecho achado pelo BM25 tenha também o seu cosseno: é ele que o limiar usa.
        pares = self.store.similarity_search_with_relevance_scores(pergunta, k=max(self._total, self.k))
        por_id: dict[str, Trecho] = {}
        for doc, score in pares:
            por_id[doc.id or doc.metadata.get("chunk_id", "")] = para_trecho(doc, score)
        lexical = [i for i in indice.ranking(pergunta) if i in por_id]
        return [por_id[i] for i in fundir_rrf(list(por_id), lexical)[:self.k]]

    def recuperar(self, pergunta: str) -> list[Trecho]:
        return [t for t in self.buscar_tudo(pergunta) if t.score >= self.limiar]

    def descrever(self) -> dict:
        d = {"k": self.k, "limiar": self.limiar, "metrica": vector_store.METRICA,
             "colecao": vector_store.NOME_COLECAO, "modo": self.modo}
        if self.modo == "hibrido":
            d |= {"fusao": f"RRF k={RRF_K}", "lexical": f"BM25 k1={BM25_K1} b={BM25_B}"}
        return d
