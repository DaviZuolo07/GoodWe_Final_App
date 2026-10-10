"""
Interface web do GoodWe ChargeOps (Aula 08) — Gradio sobre o `ChatbotRAG`.

    python app/main.py            # http://127.0.0.1:7860
    python app/main.py --share    # URL pública temporária (cuidado: usa a SUA chave)

O QUE VALE PONTO AQUI É A CITAÇÃO VISÍVEL (bloco A). Por isso, além da citação
no texto (destacada como etiqueta no balão), cada resposta atualiza o painel de
grounding: medidor com o score do melhor trecho contra o limiar, a trilha do
pipeline (moderação → busca → modelo → citação) com a etapa onde a pergunta
parou, e um cartão por fonte com documento, página (page + 1), categoria,
score e o trecho recuperado. Quando o bot recusa, o painel mostra por quê:
nada passou do limiar, ou passou e o modelo não achou a resposta nos trechos.
É o grounding demonstrado na tela.

POR QUE O VISUAL É O DO SEMS+: é o app da GoodWe que o síndico e o instalador já
usam para monitorar o carregador HCA G2 (o datasheet cita o SEMS+ como o app de
gestão). Fundo grafite, cartões com borda fina, vermelho GoodWe só para destaque,
KPIs em tiles e um medidor semicircular. O medidor do SEMS+ mostra potência; o
nosso mostra relevância, que é o "quanto de energia" que a resposta tem da base.

POR QUE A INTERFACE NÃO TEM LÓGICA DE RAG: ela chama `ChatbotRAG.responder_stream`,
o mesmo pipeline (guardrails -> retriever -> prompt -> pós-processamento) que o
eval mede. Uma interface com regra própria entregaria respostas que o RAGAS
nunca viu. O destaque da citação é só apresentação: o texto guardado no
histórico é o `RespostaRAG.texto`, sem alteração.

MEMÓRIA POR SESSÃO: `gr.State(uuid4)` dá um id por aba e o `store` guarda um
`ChatMessageHistory` por id (Aula 08). O histórico NÃO entra no prompt RAG — o
prompt medido no eval é sem histórico, e histórico crescente degrada o grounding
(context rot, Aula 13). Ele é usado para uma coisa só: pergunta de continuação
curta ("e o de 11 kW?") ganha a pergunta anterior, para que o retriever e o
modelo saibam do que se trata. O botão "Nova conversa" zera o histórico da sessão.

SEGURANÇA: a chave vem do `.env` via `os.getenv` (dentro de `src.chain.llm`) e
nunca aparece na tela, nem em mensagem de erro. `share` é falso por padrão.
Todo texto vindo de documento ou do usuário passa por `html.escape` antes de
entrar no painel: um PDF com `<script>` aparece como texto, não executa.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import re
import sys
import uuid
from pathlib import Path

# Sem isto, um venv criado no 3.14 por cima de um 3.13 quebra no `import numpy`
# com "_multiarray_umath ... cp313", que não diz nada sobre a causa real.
if sys.version_info[:2] != (3, 13):
    sys.exit(f"Python {sys.version_info.major}.{sys.version_info.minor} detectado; o projeto exige 3.13 "
             "(o ragas não instala no 3.14). Recrie o venv: rmdir /s /q venv && py -3.13 -m venv venv")

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import gradio as gr  # noqa: E402
from langchain_community.chat_message_histories import ChatMessageHistory  # noqa: E402

from src.chain.llm import descrever as descrever_llm  # noqa: E402
from src.chain.rag import PERFIL_LLM, ChatbotRAG  # noqa: E402
from src.rag import prompt_rag, retriever, vector_store  # noqa: E402
from src.schemas.resultados import RespostaRAG  # noqa: E402

TITULO = "GoodWe ChargeOps"
MAX_CARACTERES = 500          # entrada longa só gasta token e abre espaço para injection
CARREGANDO = "⏳ Buscando nos documentos..."
ERRO_MODELO = ("⚠️ Não consegui falar com o modelo agora (Ollama Cloud fora do ar, lento ou sem cota). "
               "Tente de novo em alguns segundos. Se persistir, rode `python -m src.teste_auth`.")

EXEMPLOS = [
    "Qual a potência do GW22K-HCA-20?",
    "Encostei o cartão e a luz vermelha acendeu por 2 segundos. O que fiz de errado?",
    "Quanto vou pagar por uma recarga de 30 kWh?",
    "Por quanto tempo posso reservar a vaga?",
    "Qual a previsão do tempo para amanhã em São Paulo?",
]

_CONTINUACAO = re.compile(r"^(e|mas|e se|e o|e a|e os|e as|e quanto|e qual|e no|e na|tamb[eé]m)\b", re.I)

store: dict[str, ChatMessageHistory] = {}
_bot: ChatbotRAG | None = None


def bot() -> ChatbotRAG:
    """Criado na primeira pergunta: abrir o Chroma e o cliente do modelo não pode travar o import."""
    global _bot
    if _bot is None:
        _bot = ChatbotRAG()
    return _bot


def historico(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


def pergunta_efetiva(pergunta: str, hist: ChatMessageHistory) -> str:
    """Pergunta de continuação curta herda a pergunta anterior do usuário."""
    anteriores = [m.content for m in hist.messages if m.type == "human"]
    if anteriores and len(pergunta.split()) <= 6 and _CONTINUACAO.match(pergunta.strip()):
        return f"{anteriores[-1]} {pergunta}"
    return pergunta


# --------------------------------------------------------------------------- #
# apresentação da resposta
# --------------------------------------------------------------------------- #
def destacar_citacoes(texto: str) -> str:
    """`(fonte: doc, página X)` vira código inline, que o CSS desenha como etiqueta. O texto não muda."""
    return re.sub(r"\(fonte:[^()]+?\)", lambda m: f"`{m.group(0)}`", texto or "")


def _e(texto) -> str:
    return html.escape(str(texto), quote=True)


ROTULOS_ROTA = {
    "rag": ("Respondido com fonte", "ok"),
    "recusa_llm": ("Sem a resposta nos trechos", "alerta"),
    "sem_contexto": ("Nada relevante na base", "alerta"),
    "recusa_escopo": ("Encaminhado a profissional", "info"),
    "bloqueio_moderacao": ("Bloqueado pela moderação", "erro"),
    "apresentacao": ("Apresentação do assistente", "info"),
}


def _medidor(score: float | None, limiar: float) -> str:
    """Medidor semicircular no estilo do SEMS+: marcas de 0 a 1, acesas até o score."""
    marcas, n = [], 36
    for i in range(n + 1):
        frac = i / n
        ang = 3.14159265 * (1 - frac)
        x1, y1 = 100 + 74 * _cos(ang), 100 - 74 * _sin(ang)
        x2, y2 = 100 + 86 * _cos(ang), 100 - 86 * _sin(ang)
        aceso = score is not None and frac <= score
        classe = "m-on" if aceso else "m-off"
        if aceso and frac < limiar:
            classe = "m-baixo"
        marcas.append(f'<line class="{classe}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    ang = 3.14159265 * (1 - limiar)
    lx1, ly1 = 100 + 64 * _cos(ang), 100 - 64 * _sin(ang)
    lx2, ly2 = 100 + 94 * _cos(ang), 100 - 94 * _sin(ang)
    valor = "—" if score is None else f"{score:.3f}"
    return (
        '<svg class="medidor" viewBox="0 0 200 118" role="img" '
        f'aria-label="Relevância do melhor trecho: {valor}; limiar {limiar:.2f}">'
        + "".join(marcas)
        + f'<line class="m-limiar" x1="{lx1:.1f}" y1="{ly1:.1f}" x2="{lx2:.1f}" y2="{ly2:.1f}"/>'
        + f'<text class="m-valor" x="100" y="92" text-anchor="middle">{valor}</text>'
        + '<text class="m-rotulo" x="100" y="110" text-anchor="middle">relevância do melhor trecho</text>'
        + "</svg>")


def _cos(a: float) -> float:
    import math
    return math.cos(a)


def _sin(a: float) -> float:
    import math
    return math.sin(a)


def _trilha(r: RespostaRAG | None) -> str:
    """Moderação → Busca → Modelo → Citação, com o estado de cada etapa nesta resposta."""
    etapas = ["Moderação", "Busca", "Modelo", "Citação"]
    if r is None:
        estados = ["idle"] * 4
    elif r.rota == "bloqueio_moderacao":
        estados = ["erro", "idle", "idle", "idle"]
    elif r.rota in ("apresentacao",) or (r.rota == "recusa_escopo" and not r.fontes and not r.descartados):
        estados = ["ok", "idle", "idle", "idle"]
    elif r.rota in ("sem_contexto",) or (r.rota == "recusa_escopo" and not r.fontes):
        estados = ["ok", "alerta", "idle", "idle"]
    elif r.rota in ("recusa_llm", "recusa_escopo"):
        estados = ["ok", "ok", "alerta", "idle"]
    else:
        estados = ["ok", "ok", "ok", "ok" if r.citacoes else "alerta"]
    itens = []
    for nome, est in zip(etapas, estados):
        itens.append(f'<div class="etapa {est}"><span class="ponto"></span>{nome}</div>')
    return '<div class="trilha">' + '<span class="liga"></span>'.join(itens) + "</div>"


def _tile(valor, rotulo: str, extra: str = "") -> str:
    return (f'<div class="tile {extra}"><div class="tile-valor">{_e(valor)}</div>'
            f'<div class="tile-rotulo">{_e(rotulo)}</div></div>')


def _cartao_fonte(n: int, f: dict, citada: bool = False) -> str:
    trecho = " ".join(f["trecho"].split())
    largura = max(0.0, min(1.0, float(f["score"]))) * 100
    selo = '<span class="selo-citada">citada</span>' if citada else ""
    return (
        '<div class="fonte">'
        f'<div class="fonte-topo"><span class="fonte-n">{n:02d}</span>'
        f'<span class="fonte-doc">{_e(f["documento"])}</span>{selo}</div>'
        f'<div class="fonte-meta">página {_e(f["pagina"])} · categoria <code>{_e(f.get("categoria", ""))}</code>'
        f' · score <b>{float(f["score"]):.3f}</b></div>'
        f'<div class="barra"><span style="width:{largura:.0f}%"></span></div>'
        f'<blockquote>{_e(trecho)}</blockquote>'
        "</div>")


def painel_fontes(r: RespostaRAG | None) -> str:
    """Painel de grounding: medidor, trilha do pipeline, KPIs da resposta e fontes."""
    limiar = retriever.LIMIAR
    if r is None:
        return ('<div class="painel">' + _medidor(None, limiar) + _trilha(None)
                + '<p class="vazio">As fontes da última resposta aparecem aqui: documento, página, '
                  'categoria, score e o trecho usado.</p></div>')

    melhores = [f["score"] for f in (r.fontes or r.descartados)]
    score = max(melhores) if melhores else None
    rotulo, tom = ROTULOS_ROTA.get(r.rota, (r.rota, "info"))
    citadas = {(d, p) for d, p in prompt_rag.extrair_citacoes(r.texto)}
    docs_citados = len({d for d, _ in citadas})
    partes = [
        '<div class="painel">',
        _medidor(score, limiar),
        f'<div class="status {tom}"><span class="ponto"></span>{_e(rotulo)}</div>',
        _trilha(r),
        '<div class="tiles">',
        _tile(len(r.fontes), "trechos usados"),
        _tile(docs_citados, "documentos citados"),
        _tile(f"{limiar:.2f}", "limiar de relevância"),
        _tile(r.tokens_servidor_saida or "—", "tokens gerados"),
        "</div>",
    ]

    if r.rota == "bloqueio_moderacao":
        partes.append(f'<p class="nota erro">🛡️ <b>Pergunta bloqueada pela moderação de entrada</b> '
                      f'({_e(r.categoria_guardrail)}). Nenhum documento foi consultado.</p>')
    elif r.rota == "apresentacao":
        partes.append('<p class="nota">Pergunta sobre o próprio assistente: resposta fixa, '
                      'nenhum documento foi consultado e nenhuma especificação foi citada.</p>')
    elif r.rota == "recusa_escopo" and not r.fontes and not r.descartados:
        partes.append(f'<p class="nota">🛡️ <b>Resposta fixa de segurança</b> ({_e(r.categoria_guardrail)}). '
                      "Nenhum documento foi consultado.</p>")
    elif r.fontes:
        titulo = {"rag": f"✅ <b>Trechos enviados ao modelo</b> (acima do limiar de relevância {limiar:.2f})",
                  "recusa_llm": f"⚠️ <b>Trechos acima do limiar {limiar:.2f}, mas sem a resposta</b> — "
                                "o modelo recusou em vez de inventar",
                  "recusa_escopo": f"⚠️ <b>Trechos acima do limiar {limiar:.2f}, mas sem a resposta</b> — "
                                   "pergunta encaminhada a profissional habilitado"
                  }.get(r.rota, f"Trechos ({limiar:.2f})")
        partes.append(f'<p class="nota">{titulo}</p>')
        partes.append('<div class="lista-fontes">' + "".join(
            _cartao_fonte(n, f, (f["documento"], f["pagina"]) in citadas) for n, f in enumerate(r.fontes, 1))
            + "</div>")
    else:
        partes.append(f'<p class="nota alerta">🚫 <b>Nenhum trecho passou do limiar de relevância '
                      f'({limiar:.2f}).</b> O modelo não foi chamado: sem contexto, a resposta é a recusa.</p>')

    if r.descartados:
        partes.append(f'<details><summary>Abaixo do limiar ({limiar:.2f}), não usados: {len(r.descartados)}'
                      "</summary>" + "".join(_cartao_fonte(n, f) for n, f in enumerate(r.descartados, 1))
                      + "</details>")
    if r.descartados_por_injecao:
        partes.append('<p class="nota erro">🛡️ <b>Removidos por suspeita de injection via documento:</b> '
                      + "; ".join(f"{_e(f['documento'])} p. {_e(f['pagina'])} ({_e(f['motivo'])})"
                                  for f in r.descartados_por_injecao) + "</p>")
    if r.citacao_adicionada:
        partes.append('<p class="nota">ℹ️ O modelo não citou a fonte; a citação do trecho mais similar foi anexada.</p>')
    if r.citacoes_invalidas:
        partes.append(f'<p class="nota alerta">⚠️ Citações que não vieram do retriever: '
                      f'{_e(", ".join(r.citacoes_invalidas))}</p>')
    partes.append("</div>")
    return "".join(partes)


def painel_carregando(etapa: str) -> str:
    return (f'<div class="painel">{_medidor(None, retriever.LIMIAR)}'
            f'<div class="status info pulsando"><span class="ponto"></span>{_e(etapa)}</div></div>')


# --------------------------------------------------------------------------- #
# eventos
# --------------------------------------------------------------------------- #
def chat(mensagem: str, _historico_tela: list, session_id: str):
    """Gerador do ChatInterface: (texto parcial, painel de grounding)."""
    pergunta = (mensagem or "").strip()[:MAX_CARACTERES]
    if not pergunta:
        yield "Digite uma pergunta sobre recarga no condomínio.", painel_fontes(None)
        return
    hist = historico(session_id)
    yield CARREGANDO, painel_carregando("Buscando trechos relevantes...")
    final: RespostaRAG | None = None
    try:
        for tipo, valor in bot().responder_stream(pergunta_efetiva(pergunta, hist)):
            if tipo == "parcial":
                yield valor, painel_carregando("Gerando resposta a partir dos trechos recuperados...")
            else:
                final = valor
    except Exception as e:  # nunca traceback na tela, nunca a chave
        yield ERRO_MODELO, f'<div class="painel"><p class="nota erro">Erro técnico: <code>{_e(type(e).__name__)}</code></p></div>'
        return
    if final is None:
        yield ERRO_MODELO, painel_fontes(None)
        return
    hist.add_user_message(pergunta)
    hist.add_ai_message(final.texto)
    yield destacar_citacoes(final.texto), painel_fontes(final)


def nova_conversa(session_id: str):
    """Zera as TRÊS cópias do histórico, não só a da tela.

    O `gr.ChatInterface` (Gradio 6) não lê o `Chatbot` visível ao enviar: ele lê
    um `gr.State` interno (`chatbot_state`) e o sincroniza depois. Limpar só o
    `Chatbot` apagava a tela, mas a próxima mensagem ou exemplo clicado
    re-renderizava a conversa antiga a partir desse estado. Por isso a saída
    inclui `chatbot_state` e `chatbot_value`, além do `store` da memória RAG.
    """
    store.pop(session_id, None)
    return [], [], [], painel_fontes(None), str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# layout
# --------------------------------------------------------------------------- #
def _logo_data_uri() -> str:
    """Logo com o fundo branco transparente, para o vermelho ficar sobre o grafite como no SEMS+."""
    caminho = RAIZ / "assets" / "goodwe_logo.png"
    try:
        from PIL import Image
        im = Image.open(caminho).convert("RGBA")
        im.putdata([(r, g, b, 0) if r > 235 and g > 235 and b > 235 else (r, g, b, a)
                    for r, g, b, a in im.getdata()])
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        dados = buf.getvalue()
    except Exception:
        dados = caminho.read_bytes()
    return "data:image/png;base64," + base64.b64encode(dados).decode()


def _kpis_base() -> list[tuple[str, str]]:
    """Números do índice lidos do Chroma local (sem rede). Se o índice não abrir, a tela sobe mesmo assim."""
    try:
        est = vector_store.estatisticas(vector_store.abrir())
        docs, chunks, cats = str(len(est["por_documento"])), str(est["chunks"]), str(len(est["por_categoria"]))
    except Exception:
        docs = chunks = cats = "—"
    try:
        modelo = descrever_llm(perfil=PERFIL_LLM)["model"]
    except Exception:
        modelo = "—"
    busca = "Híbrida" if retriever.MODO == "hibrido" else "Vetorial"
    return [(docs, "documentos indexados"), (chunks, "trechos no ChromaDB"), (cats, "categorias"),
            (f"{busca} · k={retriever.K}", "busca BM25 + vetor" if retriever.MODO == "hibrido" else "cosseno"),
            (str(modelo), "modelo · temperature 0")]


def cabecalho() -> str:
    return f"""
<header class="topo">
  <div class="marca">
    <img src="{_logo_data_uri()}" alt="GoodWe" class="logo"/>
    <span class="divisor"></span>
    <div class="produto"><span class="nome">ChargeOps</span><span class="sub">assistente de recarga EV · condomínio</span></div>
  </div>
  <div class="online"><span class="ponto"></span>RAG online · responde só com os documentos e cita a página</div>
</header>
<section class="kpis">{''.join(_tile(v, r, "kpi") for v, r in _kpis_base())}</section>
"""


CSS_PATH = Path(__file__).with_name("tema_sems.css")


def tema() -> gr.themes.Base:
    return gr.themes.Base(
        primary_hue=gr.themes.Color(c50="#fff1f1", c100="#ffdfe0", c200="#ffc5c7", c300="#ff9da0",
                                    c400="#ff6468", c500="#f8333a", c600="#e60012", c700="#c1000f",
                                    c800="#9f0612", c900="#830c15", c950="#480005"),
        neutral_hue=gr.themes.Color(c50="#f4f6fa", c100="#e6e9f0", c200="#c9ceda", c300="#a3aabb",
                                    c400="#7b8397", c500="#5d6579", c600="#454c5e", c700="#2c3240",
                                    c800="#1b1f29", c900="#12151c", c950="#0a0c11"),
        font=[gr.themes.GoogleFont("Inter"), "Segoe UI", "system-ui", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "Consolas", "monospace"],
        radius_size=gr.themes.sizes.radius_lg,
    ).set(
        body_background_fill="#07090d", body_background_fill_dark="#07090d",
        body_text_color="#e8ebf2", body_text_color_dark="#e8ebf2",
        background_fill_primary="#11141b", background_fill_primary_dark="#11141b",
        background_fill_secondary="#171b24", background_fill_secondary_dark="#171b24",
        block_background_fill="#11141b", block_background_fill_dark="#11141b",
        block_border_color="#232836", block_border_color_dark="#232836",
        border_color_primary="#232836", border_color_primary_dark="#232836",
        input_background_fill="#0d1016", input_background_fill_dark="#0d1016",
        input_border_color="#2a3040", input_border_color_dark="#2a3040",
        input_border_color_focus="#e60012", input_border_color_focus_dark="#e60012",
        button_primary_background_fill="#e60012", button_primary_background_fill_dark="#e60012",
        button_primary_background_fill_hover="#ff1f2f", button_primary_background_fill_hover_dark="#ff1f2f",
        button_primary_text_color="#ffffff", button_primary_text_color_dark="#ffffff",
        button_secondary_background_fill="#171b24", button_secondary_background_fill_dark="#171b24",
        button_secondary_background_fill_hover="#1f2430", button_secondary_background_fill_hover_dark="#1f2430",
        button_secondary_text_color="#e8ebf2", button_secondary_text_color_dark="#e8ebf2",
        button_secondary_border_color="#2a3040", button_secondary_border_color_dark="#2a3040",
        color_accent="#e60012", color_accent_soft="#2a1014", color_accent_soft_dark="#2a1014",
        link_text_color="#ff5a63", link_text_color_dark="#ff5a63",
        block_label_text_color="#8b93a7", block_label_text_color_dark="#8b93a7",
        block_title_text_color="#e8ebf2", block_title_text_color_dark="#e8ebf2",
        code_background_fill="#1d2230", code_background_fill_dark="#1d2230",
    )


def montar_interface() -> gr.Blocks:
    with gr.Blocks(title=TITULO, fill_width=True) as demo:
        sid = gr.State(lambda: str(uuid.uuid4()))
        gr.HTML(cabecalho(), elem_id="cabecalho")
        with gr.Row(equal_height=False, elem_id="area"):
            with gr.Column(scale=7, elem_classes=["cartao"]):
                gr.HTML('<div class="cartao-titulo"><span class="icone">⚡</span>Conversa'
                        '<span class="dica">manual e datasheet HCA G2 · FAQ · regimento · tarifa</span></div>')
                painel = gr.HTML(painel_fontes(None), render=False, elem_id="painel")
                chatbot = gr.Chatbot(height=520, show_label=False, elem_id="chat", layout="bubble",
                                     placeholder="<div class='boas-vindas'><b>Olá! Sou o ChargeOps.</b><br>"
                                                 "Pergunte sobre o carregador GoodWe HCA G2, a recarga, "
                                                 "o regimento ou a tarifa do condomínio.<br>"
                                                 "Toda resposta vem com a fonte: documento e página.</div>")
                conversa = gr.ChatInterface(
                    fn=chat,
                    chatbot=chatbot,
                    textbox=gr.Textbox(placeholder="Pergunte sobre o carregador, a recarga, o regimento ou a tarifa...",
                                       max_lines=5, submit_btn=True, show_label=False, elem_id="entrada"),
                    additional_inputs=[sid],
                    additional_outputs=[painel],
                    examples=[[e] for e in EXEMPLOS],
                    run_examples_on_click=True,
                    cache_examples=False,
                    flagging_mode="never",
                )
                limpar = gr.Button("Nova conversa · limpa a memória desta sessão", variant="secondary",
                                   elem_id="limpar")
            with gr.Column(scale=5, elem_classes=["cartao"]):
                gr.HTML('<div class="cartao-titulo"><span class="icone">📄</span>Grounding'
                        '<span class="dica">de onde veio a última resposta</span></div>')
                painel.render()
        gr.HTML('<footer class="rodape">EV Challenge 2026 · FIAP × GoodWe Brasil · '
                'documentos de condomínio fictício de demonstração · a chave do modelo nunca sai do servidor</footer>')
        limpar.click(nova_conversa, inputs=[sid],
                     outputs=[chatbot, conversa.chatbot_state, conversa.chatbot_value, painel, sid],
                     queue=False)
    return demo


def opcoes_visuais() -> dict:
    """Tema e CSS do `launch` (no Gradio 6 eles saíram do `gr.Blocks`). Usado também pelas capturas."""
    return {"theme": tema(), "css": CSS_PATH.read_text(encoding="utf-8")}


def main():
    ap = argparse.ArgumentParser(description="Interface Gradio do GoodWe ChargeOps")
    ap.add_argument("--share", action="store_true", help="gera URL pública temporária (usa a sua chave)")
    ap.add_argument("--porta", type=int, default=7860)
    a = ap.parse_args()
    montar_interface().launch(share=a.share, server_port=a.porta, inbrowser=False, **opcoes_visuais())


if __name__ == "__main__":
    main()
