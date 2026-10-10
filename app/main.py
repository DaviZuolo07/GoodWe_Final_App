"""
Interface web do GoodWe ChargeOps (Aula 08) — Gradio sobre o `ChatbotRAG`.

    python app/main.py            # http://127.0.0.1:7860
    python app/main.py --share    # URL pública temporária (cuidado: usa a SUA chave)

O QUE VALE PONTO AQUI É A CITAÇÃO VISÍVEL (bloco A). Por isso, além da citação
no texto, cada resposta atualiza o painel "Fontes consultadas" com documento,
página (page + 1), categoria, score de similaridade e o trecho recuperado.
Quando o bot recusa, o painel mostra por quê: nada passou do limiar, ou passou
e o modelo não achou a resposta nos trechos — é o grounding demonstrado na tela.

POR QUE A INTERFACE NÃO TEM LÓGICA DE RAG: ela chama `ChatbotRAG.responder_stream`,
o mesmo pipeline (guardrails -> retriever -> prompt -> pós-processamento) que o
eval mede. Uma interface com regra própria entregaria respostas que o RAGAS
nunca viu.

MEMÓRIA POR SESSÃO: `gr.State(uuid4)` dá um id por aba e o `store` guarda um
`ChatMessageHistory` por id (Aula 08). O histórico NÃO entra no prompt RAG — o
prompt medido no eval é sem histórico, e histórico crescente degrada o grounding
(context rot, Aula 13). Ele é usado para uma coisa só: pergunta de continuação
curta ("e o de 11 kW?") ganha a pergunta anterior, para que o retriever e o
modelo saibam do que se trata. O botão "Nova conversa" zera o histórico da sessão.

SEGURANÇA: a chave vem do `.env` via `os.getenv` (dentro de `src.chain.llm`) e
nunca aparece na tela, nem em mensagem de erro. `share` é falso por padrão.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import gradio as gr  # noqa: E402
from langchain_community.chat_message_histories import ChatMessageHistory  # noqa: E402

from src.chain.rag import ChatbotRAG  # noqa: E402
from src.rag import retriever  # noqa: E402
from src.schemas.resultados import RespostaRAG  # noqa: E402

TITULO = "GoodWe ChargeOps"
MAX_CARACTERES = 500          # entrada longa só gasta token e abre espaço para injection
CARREGANDO = "⏳ Buscando nos documentos..."
ERRO_MODELO = ("⚠️ Não consegui falar com o modelo agora (Ollama Cloud fora do ar, lento ou sem cota). "
               "Tente de novo em alguns segundos. Se persistir, rode `python -m src.teste_auth`.")
PAINEL_VAZIO = "_As fontes da última resposta aparecem aqui._"

EXEMPLOS = [
    "Qual a potência nominal de saída do GW22K-HCA-20?",
    "Encostei o cartão e a luz vermelha acendeu por 2 segundos. O que fiz de errado?",
    "Quanto vou pagar por uma recarga de 30 kWh?",
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


def _cartao_fonte(n: int, f: dict) -> str:
    trecho = " ".join(f["trecho"].split())
    return (f"**{n}. {f['documento']}** — página {f['pagina']} · categoria `{f.get('categoria', '')}` · "
            f"score **{f['score']:.3f}**\n\n> {trecho}")


def painel_fontes(r: RespostaRAG) -> str:
    limiar = retriever.LIMIAR
    if r.rota == "bloqueio_moderacao":
        return (f"🛡️ **Pergunta bloqueada pela moderação de entrada** ({r.categoria_guardrail}). "
                "Nenhum documento foi consultado.")
    if r.rota == "recusa_escopo" and not r.fontes and not r.descartados:
        return f"🛡️ **Resposta fixa de segurança** ({r.categoria_guardrail}). Nenhum documento foi consultado."

    partes = []
    if r.fontes:
        titulo = {"rag": "✅ **Trechos enviados ao modelo** (acima do limiar de relevância {:.2f})",
                  "recusa_llm": "⚠️ **Trechos acima do limiar {:.2f}, mas sem a resposta** — o modelo recusou "
                                "em vez de inventar",
                  "recusa_escopo": "⚠️ **Trechos acima do limiar {:.2f}, mas sem a resposta** — "
                                   "pergunta encaminhada a profissional habilitado"}.get(r.rota, "Trechos ({:.2f})")
        partes.append(titulo.format(limiar))
        partes.extend(_cartao_fonte(n, f) for n, f in enumerate(r.fontes, 1))
    else:
        partes.append(f"🚫 **Nenhum trecho passou do limiar de relevância ({limiar:.2f}).** "
                      "O modelo não foi chamado: sem contexto, a resposta é a recusa.")
    if r.descartados:
        partes.append(f"<details><summary>Abaixo do limiar ({limiar:.2f}), não usados: "
                      f"{len(r.descartados)}</summary>\n\n"
                      + "\n\n".join(_cartao_fonte(n, f) for n, f in enumerate(r.descartados, 1))
                      + "\n\n</details>")
    if r.descartados_por_injecao:
        partes.append("🛡️ **Removidos por suspeita de injection via documento:** "
                      + "; ".join(f"{f['documento']} p. {f['pagina']} ({f['motivo']})"
                                  for f in r.descartados_por_injecao))
    if r.citacao_adicionada:
        partes.append("ℹ️ O modelo não citou a fonte; a citação do trecho mais similar foi anexada.")
    if r.citacoes_invalidas:
        partes.append(f"⚠️ Citações que não vieram do retriever: {', '.join(r.citacoes_invalidas)}")
    return "\n\n".join(partes)


def chat(mensagem: str, _historico_tela: list, session_id: str):
    """Gerador do ChatInterface: (texto parcial, painel de fontes)."""
    pergunta = (mensagem or "").strip()[:MAX_CARACTERES]
    if not pergunta:
        yield "Digite uma pergunta sobre recarga no condomínio.", PAINEL_VAZIO
        return
    hist = historico(session_id)
    yield CARREGANDO, "_Buscando trechos relevantes..._"
    final: RespostaRAG | None = None
    try:
        for tipo, valor in bot().responder_stream(pergunta_efetiva(pergunta, hist)):
            if tipo == "parcial":
                yield valor, "_Gerando resposta a partir dos trechos recuperados..._"
            else:
                final = valor
    except Exception as e:  # nunca traceback na tela, nunca a chave
        yield ERRO_MODELO, f"Erro técnico: `{type(e).__name__}`"
        return
    if final is None:
        yield ERRO_MODELO, PAINEL_VAZIO
        return
    hist.add_user_message(pergunta)
    hist.add_ai_message(final.texto)
    yield final.texto, painel_fontes(final)


def nova_conversa(session_id: str):
    store.pop(session_id, None)
    return [], PAINEL_VAZIO, str(uuid.uuid4())


def montar_interface() -> gr.Blocks:
    with gr.Blocks(title=TITULO) as demo:
        sid = gr.State(lambda: str(uuid.uuid4()))
        with gr.Row():
            gr.Image(str(RAIZ / "assets" / "goodwe_logo.png"), show_label=False, container=False,
                     height=48, width=160, interactive=False, buttons=[])
        gr.Markdown(
            "## ⚡ GoodWe ChargeOps — assistente de recarga de veículos elétricos em condomínio\n"
            "Responde **somente** com base nos documentos indexados (manual e datasheet do GoodWe HCA G2, "
            "FAQ, regimento e tabela tarifária do condomínio de demonstração) e cita documento e página. "
            "Sem a informação nos documentos, ele diz que não encontrou.")
        with gr.Row():
            with gr.Column(scale=3):
                fontes = gr.Markdown(PAINEL_VAZIO, render=False)
                chatbot = gr.Chatbot(height=460, label="Conversa")
                gr.ChatInterface(
                    fn=chat,
                    chatbot=chatbot,
                    textbox=gr.Textbox(placeholder="Pergunte sobre o carregador, a recarga, o regimento ou a tarifa...",
                                       max_lines=5, submit_btn=True),
                    additional_inputs=[sid],
                    additional_outputs=[fontes],
                    examples=[[e] for e in EXEMPLOS],
                    run_examples_on_click=True,
                    cache_examples=False,
                    flagging_mode="never",
                )
                limpar = gr.Button("🧹 Nova conversa (limpa a memória desta sessão)", variant="secondary")
            with gr.Column(scale=2):
                with gr.Accordion("📄 Fontes consultadas", open=True):
                    fontes.render()
        limpar.click(nova_conversa, inputs=[sid], outputs=[chatbot, fontes, sid])
    return demo


def main():
    ap = argparse.ArgumentParser(description="Interface Gradio do GoodWe ChargeOps")
    ap.add_argument("--share", action="store_true", help="gera URL pública temporária (usa a sua chave)")
    ap.add_argument("--porta", type=int, default=7860)
    a = ap.parse_args()
    montar_interface().launch(share=a.share, server_port=a.porta, inbrowser=False)


if __name__ == "__main__":
    main()
