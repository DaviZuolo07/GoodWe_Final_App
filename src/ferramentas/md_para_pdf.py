"""
Markdown -> PDF com PyMuPDF (`pymupdf.Story`), sem dependência nova.

    python -m src.ferramentas.md_para_pdf base        # regenera os PDFs da base a partir de data/knowledge_base/fontes/
    python -m src.ferramentas.md_para_pdf relatorio   # docs/relatorio_evolucao.md -> docs/relatorio_evolucao.pdf

POR QUE GERAR O PDF EM VEZ DE ESCREVER DIRETO NO EDITOR:
os documentos elaborados pelo grupo (FAQ, regimento, tarifa) e o relatório de
evolução têm a fonte em Markdown versionada no git. O PDF é derivado: quem
revisa lê o diff do `.md`, e o PDF indexado no ChromaDB sempre bate com a
fonte. O `pymupdf` já é dependência do loader (Aula 06) e gera PDF com TEXTO
selecionável — requisito do `PyMuPDFLoader`, que não lê PDF escaneado.

Conversor deliberadamente pequeno: títulos `#`, parágrafos, listas `-`,
**negrito**, `código` e tabelas `| a | b |`. É o subconjunto que os
documentos usam; Markdown fora dele sai como texto.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import pymupdf

RAIZ = Path(__file__).resolve().parents[2]
PASTA_FONTES = RAIZ / "data" / "knowledge_base" / "fontes"
PASTA_BASE = RAIZ / "data" / "knowledge_base"

CSS = """
* { font-family: sans-serif; }
body { font-size: 10pt; line-height: 1.35; }
h1 { font-size: 15pt; margin-bottom: 6pt; }
h2 { font-size: 12pt; margin-top: 10pt; margin-bottom: 4pt; }
h3 { font-size: 10.5pt; margin-top: 8pt; margin-bottom: 3pt; }
p { margin-top: 0; margin-bottom: 5pt; text-align: justify; }
li { margin-bottom: 2pt; }
table { border-collapse: collapse; margin-bottom: 6pt; }
td, th { border: 0.5pt solid #888; padding: 2pt 4pt; font-size: 8.5pt; vertical-align: top; }
th { background-color: #e8eef5; }
code { font-family: monospace; font-size: 8.5pt; }
"""

MARGEM = 46            # pt (~1,6 cm)
A4 = pymupdf.paper_rect("a4")


def _inline(texto: str) -> str:
    t = html.escape(texto, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    return t


def md_para_html(md: str) -> str:
    linhas = md.splitlines()
    saida: list[str] = []
    i = 0
    while i < len(linhas):
        linha = linhas[i].rstrip()
        if not linha.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", linha)
        if m:
            n = len(m.group(1))
            saida.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if linha.lstrip().startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                bloco.append(linhas[i].strip())
                i += 1
            linhas_tab = [l for l in bloco if not re.match(r"^\|[\s:|-]+\|$", l)]
            partes = ["<table>"]
            for n, l in enumerate(linhas_tab):
                cels = [c.strip() for c in l.strip("|").split("|")]
                tag = "th" if n == 0 else "td"
                partes.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cels) + "</tr>")
            partes.append("</table>")
            saida.append("".join(partes))
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", linha):
            ordenada = bool(re.match(r"^\s*\d+\.", linha))
            itens = []
            while i < len(linhas) and re.match(r"^\s*([-*]|\d+\.)\s+", linhas[i]):
                itens.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", linhas[i]))
                i += 1
            tag = "ol" if ordenada else "ul"
            saida.append(f"<{tag}>" + "".join(f"<li>{_inline(t)}</li>" for t in itens) + f"</{tag}>")
            continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", linha.strip())
        if m:   # imagem: caminho relativo ao .md (Story resolve pelo `archive`)
            saida.append(f'<p style="text-align:center"><img src="{m.group(2)}" width="460"/><br/>'
                         f'<i>{_inline(m.group(1))}</i></p>')
            i += 1
            continue
        if linha.strip().startswith("```"):
            i += 1
            bloco = []
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                bloco.append(html.escape(linhas[i]))
                i += 1
            i += 1
            saida.append("<p><code>" + "<br/>".join(bloco) + "</code></p>")
            continue
        paragrafo = [linha.strip()]
        i += 1
        while (i < len(linhas) and linhas[i].strip() and not re.match(r"^(#|\||\s*[-*]\s|\s*\d+\.\s|```)", linhas[i])):
            paragrafo.append(linhas[i].strip())
            i += 1
        saida.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
    return "\n".join(saida)


def converter(origem: Path, destino: Path, rodape: str | None = None) -> int:
    """Gera o PDF e devolve o número de páginas."""
    corpo = md_para_html(Path(origem).read_text(encoding="utf-8"))
    story = pymupdf.Story(html=f"<body>{corpo}</body>", user_css=CSS,
                          archive=pymupdf.Archive(str(Path(origem).resolve().parent)))
    area = A4 + (MARGEM, MARGEM, -MARGEM, -MARGEM - 14)
    writer = pymupdf.DocumentWriter(str(destino))
    mais = True
    while mais:
        dispositivo = writer.begin_page(A4)
        mais, _ = story.place(area)
        story.draw(dispositivo)
        writer.end_page()
    writer.close()

    doc = pymupdf.open(str(destino))
    if rodape:
        for n, pagina in enumerate(doc, start=1):
            pagina.insert_text((MARGEM, A4.height - MARGEM / 2), f"{rodape} · pág. {n}/{doc.page_count}",
                               fontsize=7, color=(0.4, 0.4, 0.4))
        doc.saveIncr()
    paginas = doc.page_count
    doc.close()
    return paginas


def gerar_base() -> None:
    for md in sorted(PASTA_FONTES.glob("*__*.md")):
        destino = PASTA_BASE / f"{md.stem}.pdf"
        # Sem rodapé: medido em 10/10/2026, o rodapé "<nome do arquivo> · elaborado pelo
        # grupo" entrava nos chunks e casava com perguntas sobre condomínio/recarga,
        # empurrando trechos úteis para fora do top-k. A autoria está no cabeçalho.
        n = converter(md, destino)
        print(f"{destino.relative_to(RAIZ)}: {n} página(s)")


def gerar_relatorio() -> None:
    origem = RAIZ / "docs" / "relatorio_evolucao.md"
    destino = RAIZ / "docs" / "relatorio_evolucao.pdf"
    n = converter(origem, destino, rodape="GoodWe ChargeOps · Sprint 04 · Relatório de evolução")
    print(f"{destino.relative_to(RAIZ)}: {n} página(s)")
    if n > 5:
        sys.exit(f"ERRO: o relatório tem {n} páginas; o §8 limita a 5.")


if __name__ == "__main__":
    alvo = sys.argv[1] if len(sys.argv) > 1 else "base"
    {"base": gerar_base, "relatorio": gerar_relatorio}[alvo]()
