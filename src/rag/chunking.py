"""
Chunking (Aula 06, `RecursiveCharacterTextSplitter`).

ESTRATÉGIA — e por que cada número é o que é (o §4 cobra a justificativa):

- **Dentro da página, nunca através dela.** O splitter recebe uma `Document`
  por página e cada chunk herda o metadado daquela página. Um chunk que
  atravessasse a quebra de página teria duas páginas e a citação apontaria
  para uma só — metade das vezes, a errada.

- **`TAMANHO = 1000` caracteres.** A página mediana do manual tem ~870
  caracteres: com 1000, a maioria das páginas do manual vira 1 chunk inteiro
  (tabela de RCBO, especificação de cabo e passo a passo ficam juntos). O resumo
  Modbus tem ~3.700 por página e quebra em ~4 chunks, o que separa grupos de
  registradores. ~1000 caracteres ≈ 250 tokens, bem dentro do contexto de
  8192 tokens do `nomic-embed-text`.

- **`SOBREPOSICAO = 150` (15%).** Uma frase partida ao meio aparece inteira em
  pelo menos um dos dois chunks. Mais que isso só duplica texto no top-k.

- **Separadores do maior para o menor** (parágrafo → linha → frase → palavra).
  O datasheet é uma tabela achatada em uma linha por célula: o separador `\n`
  mantém cada valor junto do rótulo que o precede sempre que cabe.

- **Limpeza mínima.** Só espaços repetidos, tabulações e linhas em branco em
  excesso. Nada de reescrever conteúdo: o trecho exibido no painel de fontes
  tem que ser reconhecível no PDF.

- **ID determinístico** (`documento:p<pagina>:c<n>`). Reindexar a mesma base
  gera os mesmos IDs, então a coleção não acumula duplicatas e um chunk citado
  no eval da iteração 1 é o mesmo chunk na iteração 2.
"""

from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

TAMANHO = 1000
SOBREPOSICAO = 150
SEPARADORES = ["\n\n", "\n", ". ", " ", ""]


def limpar_texto(texto: str) -> str:
    t = texto.replace("\t", " ").replace(" ", " ")
    t = re.sub(r"[ ]{2,}", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def criar_splitter(tamanho: int = TAMANHO, sobreposicao: int = SOBREPOSICAO) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=tamanho,
        chunk_overlap=sobreposicao,
        separators=SEPARADORES,
        length_function=len,
    )


def dividir(paginas: list[Document], tamanho: int = TAMANHO,
            sobreposicao: int = SOBREPOSICAO) -> list[Document]:
    """Páginas -> chunks com `chunk_id` estável e metadado da página preservado."""
    splitter = criar_splitter(tamanho, sobreposicao)
    chunks: list[Document] = []
    for pagina in paginas:
        limpa = Document(page_content=limpar_texto(pagina.page_content), metadata=pagina.metadata)
        for n, chunk in enumerate(splitter.split_documents([limpa])):
            m = chunk.metadata
            chunk.metadata = {**m, "chunk": n, "chunk_id": f"{m['documento']}:p{m['pagina']}:c{n}"}
            chunks.append(chunk)
    return chunks


def descrever() -> dict:
    """Parâmetros de chunking — vão no cabeçalho de todo eval (mesma régua)."""
    return {"splitter": "RecursiveCharacterTextSplitter", "chunk_size": TAMANHO,
            "chunk_overlap": SOBREPOSICAO, "separadores": SEPARADORES, "unidade": "caracteres",
            "fronteira": "pagina"}
