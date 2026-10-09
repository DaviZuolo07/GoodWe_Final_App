"""
Carga dos PDFs da base de conhecimento (Aula 06, `PyMuPDFLoader`).

Por que existe uma camada em volta do loader, em vez de chamá-lo direto:

1. **Metadado de citação nasce aqui.** O `page` do PyMuPDF é 0-indexado; a
   citação mostra `page + 1`. Fazer essa conta em um único lugar (`pagina`) evita
   o erro clássico de cada consumidor somar 1 — ou esquecer de somar.
2. **Categoria vem do nome do arquivo** (`<tipo>__<descricao>.pdf`, ver
   `data/knowledge_base/README.md`). Arquivo fora do padrão é erro, não aviso:
   um PDF sem categoria entra na busca sem poder ser filtrado nem auditado.
3. **Metadado enxuto.** O PyMuPDF devolve ~16 campos (producer, trapped,
   creationDate...). O ChromaDB guarda tudo e nada disso serve para citar; só
   polui o painel de fontes. Ficam os campos que a resposta e o eval usam.
4. **Página sem texto sai.** Capas e divisórias do manual (índices 0, 15, 59–61
   e 69) têm menos de 80 caracteres: viram chunks que casam com qualquer
   pergunta curta e empurram trechos úteis para fora do top-k.
5. **Página de sumário sai.** Medido em 09/10/2026: o sumário do manual (págs.
   3–4 do PDF) lista o título de TODAS as seções, então casava com quase toda
   pergunta e ocupava o top-k. "Qual o grau de proteção IP?" trouxe o sumário
   em 1º e 2º lugar e o modelo recusou, embora IP66/IP55 estejam nas págs. 15,
   24 e 69. O "pontilhado" do sumário não é ponto: é um glifo de preenchimento
   repetido, por isso a detecção olha qualquer caractere não alfanumérico
   repetido seguido do número da página.
"""

from __future__ import annotations

import re
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document

RAIZ = Path(__file__).resolve().parents[2]
PASTA_BASE = RAIZ / "data" / "knowledge_base"

CATEGORIAS = ("manual", "norma", "regimento", "faq", "tarifa")

# Abaixo disto a página é capa, divisória ou só figura (medido nos 3 PDFs GoodWe).
MIN_CARACTERES_PAGINA = 80

# Linha de sumário: título, 5+ repetições do mesmo caractere de preenchimento, nº de página.
_LINHA_SUMARIO = re.compile(r"([^\w\s])\1{4,}\s*\d{1,3}\s*$", re.M)
MIN_LINHAS_SUMARIO = 5

_PADRAO_NOME = re.compile(r"^(?P<categoria>[a-z]+)__(?P<descricao>[a-z0-9][a-z0-9-]*)\.pdf$")


class NomeForaDoPadrao(ValueError):
    """PDF da base sem o prefixo `<tipo>__` exigido pelo README da pasta."""


def categoria_do_arquivo(nome: str) -> str:
    m = _PADRAO_NOME.match(nome)
    if not m or m.group("categoria") not in CATEGORIAS:
        raise NomeForaDoPadrao(
            f"{nome!r} não segue '<tipo>__<descricao>.pdf' com tipo em {CATEGORIAS}. "
            "Veja data/knowledge_base/README.md."
        )
    return m.group("categoria")


def eh_sumario(texto: str) -> bool:
    return len(_LINHA_SUMARIO.findall(texto)) >= MIN_LINHAS_SUMARIO


def carregar_pdf(caminho: Path) -> list[Document]:
    """Uma `Document` por página com texto, com metadado pronto para citar."""
    caminho = Path(caminho)
    categoria = categoria_do_arquivo(caminho.name)
    paginas = []
    for doc in PyMuPDFLoader(str(caminho)).load():
        if len(doc.page_content.strip()) < MIN_CARACTERES_PAGINA or eh_sumario(doc.page_content):
            continue
        page = int(doc.metadata["page"])
        paginas.append(Document(
            page_content=doc.page_content,
            metadata={
                "documento": caminho.name,
                "categoria": categoria,
                "page": page,              # 0-indexado, como o PyMuPDF entrega
                "pagina": page + 1,        # o que a citação mostra
                "total_paginas": int(doc.metadata.get("total_pages", 0)),
            },
        ))
    return paginas


def listar_pdfs(pasta: Path = PASTA_BASE) -> list[Path]:
    return sorted(Path(pasta).glob("*.pdf"))


def carregar_base(pasta: Path = PASTA_BASE) -> list[Document]:
    """Todas as páginas úteis de todos os PDFs da pasta, em ordem de arquivo."""
    pdfs = listar_pdfs(pasta)
    if not pdfs:
        raise FileNotFoundError(f"nenhum PDF em {pasta}")
    paginas: list[Document] = []
    for pdf in pdfs:
        paginas.extend(carregar_pdf(pdf))
    return paginas
