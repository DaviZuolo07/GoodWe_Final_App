"""
Relatório de evolução do projeto (§8) em PDF, até 5 páginas.

Chamado por `python -m evals.gerar_relatorios`. O texto é fixo (decisões do
projeto); todos os números vêm do consolidado `sprint3_results.json`. Células
sem execução aparecem como "pendente".
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RAIZ = Path(__file__).resolve().parent.parent
AZUL = colors.HexColor("#0B3D6B")
CINZA = colors.HexColor("#F2F4F7")


def _estilos():
    s = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=s["BodyText"], fontName="Helvetica", fontSize=9.2,
                          leading=12.4, alignment=TA_JUSTIFY, spaceAfter=4)
    return {
        "titulo": ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=18,
                                 textColor=AZUL, alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base, fontSize=8.5, textColor=colors.HexColor("#555555"), alignment=0),
        "h": ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14,
                            textColor=AZUL, spaceBefore=8, spaceAfter=3, alignment=0),
        "p": base,
        "cel": ParagraphStyle("c", parent=base, fontSize=7.8, leading=9.6, alignment=0, spaceAfter=0),
        "celb": ParagraphStyle("cb", parent=base, fontName="Helvetica-Bold", fontSize=7.8, leading=9.6,
                               alignment=0, spaceAfter=0, textColor=colors.white),
    }


def _f(v, suf="", casas=None):
    if v is None:
        return "pendente"
    if isinstance(v, str):
        return v
    if casas is not None and isinstance(v, (int, float)):
        v = f"{v:.{casas}f}"
    return f"{v}{suf}".replace(".", ",")


def _tabela(dados, larguras, st):
    linhas = [[Paragraph(str(c), st["celb"] if i == 0 else st["cel"]) for c in lin] for i, lin in enumerate(dados)]
    t = Table(linhas, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8CDD5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def construir(c: dict) -> Path:
    st = _estilos()
    destino = RAIZ / "docs" / "relatorio_evolucao.pdf"
    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title="Relatório de evolução — Sprint 03 — GoodWe ChargeOps")
    L = doc.width
    te, t, g = c["tokens_estaticos"], c["tabela_antes_depois"], c.get("guardrails") or {}
    P = lambda txt: Paragraph(txt, st["p"])  # noqa: E731
    H = lambda txt: Paragraph(txt, st["h"])  # noqa: E731
    e = []

    e += [Paragraph("Relatório de evolução do projeto — Sprint 03", st["titulo"]),
          Paragraph(f"EV Challenge GoodWe · Prompt and Artificial Intelligence · FIAP 2026.2 · "
                    f"GoodWe ChargeOps AI Assistant · modelo principal <b>{c['modelo_principal']}</b> · "
                    f"gerado em {c['gerado_em'][:16].replace('T', ' ')}", st["sub"]), Spacer(1, 6)]

    # 1 ------------------------------------------------------------------
    e.append(H("1. Resumo da evolução"))
    e.append(P(
        "Nas Sprints 1 e 2 o chatbot era uma implementação manual: o agente montava à mão uma lista de "
        "mensagens com o system prompt, um bloco de contexto GoodWe e 11 few-shots "
        f"(<b>{te['system_legado_v0']} tokens fixos</b> reenviados em toda chamada), fazia "
        "<i>requests.post</i> no Ollama sem nenhum parâmetro de geração, guardava o histórico numa lista sem "
        "limite e deixava ao modelo tanto a aritmética de recarga quanto o respeito ao escopo."))
    e.append(P(
        "Na Sprint 03 o núcleo conversacional foi reconstruído em LangChain LCEL, com as quatro peças do "
        "Módulo 1. A chain <i>ChatPromptTemplate | ChatOllama | StrOutputParser</i> usa o system prompt "
        "versionado. A memória por sessão combina <i>RunnableWithMessageHistory</i> e "
        "<i>ConversationTokenBufferMemory</i>, com teto de 1.200 tokens. O schema Pydantic v2 "
        "<i>ConsultaRecarga</i> tem <i>field_validator</i> para números no formato brasileiro e alimenta uma "
        "calculadora determinística. O context engineering usa XML tagging, medição com tiktoken e "
        "guardrails de entrada e saída. A arquitetura resultante segue abaixo."))
    e.append(P(
        "<b>moderação → validação de escopo → RunnableBranch → extração estruturada (Pydantic) → cálculo "
        "determinístico → [prompt | LLM | parser] com memória → validação de saída</b>. O código legado em "
        "<i>ai/</i> não foi alterado: ele é o grupo de controle do comparativo."))

    # 2 ------------------------------------------------------------------
    e.append(H("2. Refatoração: decisões técnicas e trade-offs"))
    decisoes = [
        ("O LLM extrai, o Python calcula",
         "O modelo só preenche <i>ConsultaRecarga</i>; tempo, energia e custo saem de "
         "<i>src/dominio/recarga.py</i> e entram no prompt como &lt;calculo_verificado&gt;. Eficiência AC "
         "de 89,4% (faixa 85,7–92,0%), de Sears, Roberts e Glitman (IEEE SusTech, 2014). Custo: uma chamada "
         "extra de LLM nos turnos numéricos, acionada por gatilho barato para não pagar em perguntas conceituais."),
        ("Guardrails determinísticos antes do LLM",
         "Injeção, jailbreak, privilégio, fraude, domínio jurídico/financeiro/elétrico, produto fora da base "
         "e fora de escopo são resolvidos por regras auditáveis, com resposta fixa e encaminhamento a "
         "profissional. O prompt v2 é a segunda camada: spotlighting em &lt;pergunta_usuario&gt; e canário. "
         "Trade-off: regras não cobrem paráfrase infinita, por isso existe a defesa em profundidade."),
        ("Memória: janela de tokens + fatos estruturados",
         "A classe exigida poda mensagens antigas. Para não esquecer dados críticos, os fatos já validados "
         "pelo Pydantic ficam em &lt;fatos_da_sessao&gt;, fora da janela. É a política de resumo adotada: "
         "estruturada, sem chamada extra e sem risco de o resumo alucinar número. Turnos bloqueados não "
         "entram na memória (evita envenenamento do histórico)."),
        ("Régua única de tokens",
         f"tiktoken <i>{te['regua']}</i>, o tokenizador do próprio gpt-oss (antes: cl100k_base, aproximado). "
         "Tokens reais do servidor (usage_metadata) registrados à parte, pois incluem o raciocínio."),
        ("Compatibilidade LangChain 1.x",
         "<i>ConversationTokenBufferMemory</i> e <i>RunnableWithMessageHistory</i> estão marcadas como "
         "deprecated em favor do LangGraph (Módulos 3/4). Mantidas porque o escopo as exige; um adaptador "
         "(<i>HistoricoComLimiteDeTokens</i>) faz uma funcionar dentro da outra sem reescrever a poda."),
    ]
    e.append(_tabela([["Decisão", "Detalhe e trade-off"]] + [[a, b] for a, b in decisoes],
                     [3.6 * cm, L - 3.6 * cm], st))

    # 3 ------------------------------------------------------------------
    e.append(H("3. Tabela de comparativo antes/depois (mesmo eval set, 28 casos)"))
    linhas = [["Métrica", "Sprints 1/2 (manual/legado)", "LCEL cru", "Sprint 03 (LCEL) v1", "Sprint 03 (LCEL) v2 — final"]]
    defs = [("Qualidade: nota do juiz (0–2)", "nota_ponderada", "", 2),
            ("Qualidade: conformidade", "conformidade_pct", "%", 1),
            ("Tokens por turno (o200k_harmony)", "tokens_por_turno_media", "", 0),
            ("Tokens reais do servidor por turno", "tokens_servidor_por_turno_media", "", 0),
            ("Latência média (ms)", "latencia_media_ms", "", 0),
            ("Latência p90 (ms)", "latencia_p90_ms", "", 0),
            ("Acurácia do structured output (campos)", "structured_acuracia_campos_pct", "%", 1),
            ("Structured output: schema válido", "structured_schema_valido_pct", "%", 1),
            ("Turnos resolvidos sem LLM (guardrails)", "turnos_resolvidos_por_guardrail", "", 0)]
    for rot, k, suf, casas in defs:
        linhas.append([rot] + [_f(t[col].get(k), suf, casas) for col in ("legado", "lcel_cru", "v1", "v2")])
    linhas.append(["Tokens fixos do system prompt", str(te["system_legado_v0"]), "~40",
                   str(te["system_v1"]), str(te["system_v2"])])
    if g:
        linhas.append(["Guardrails: bloqueio / falso positivo", "inexistente", "inexistente",
                       f"{_f(g['taxa_bloqueio_pct'], '%')} / {_f(g['taxa_falso_positivo_pct'], '%')}",
                       f"{_f(g['taxa_bloqueio_pct'], '%')} / {_f(g['taxa_falso_positivo_pct'], '%')}"])
    e.append(_tabela(linhas, [5.0 * cm] + [(L - 5.0 * cm) / 4] * 4, st))
    e.append(Spacer(1, 3))
    e.append(P(
        "Método: um único runner e um único adaptador por coluna, mesmo eval set (v1.1), mesma régua de "
        "pontuação (v1.1) e mesmo juiz (<i>glm-5.3-flash</i>, fora dos modelos avaliados, temperatura 0). "
        "A coluna LCEL cru isola o efeito do framework sozinho; v1/v2 somam prompt, structured output e "
        "guardrails. O structured output do legado mede o caminho manual equivalente (LLMProvider do legado "
        "+ json.loads, 15 casos com gabarito), porque a Sprint 2 não tinha saída estruturada."
        + (f" Guardrails medidos offline em {g.get('ataques_e_restritos')} ataques/pedidos restritos e "
           f"{g.get('legitimas')} perguntas legítimas; encaminhamento a profissional em "
           f"{g.get('restritos_com_encaminhamento')} recusas de domínio restrito." if g else "")))

    # 4 ------------------------------------------------------------------
    e.append(H("4. Problemas encontrados e soluções"))
    probs = [
        ("Falso verde de autenticação", "GET /api/tags da ollama.com é público; o diagnóstico passava e o 401 só "
         "aparecia na chain.", "Diagnóstico passou a validar com POST /api/chat (src/teste_auth.py).",
         "Validar no endpoint que de fato exige a credencial."),
        ("Resposta vazia do modelo", "gemma4/glm-flash devolvem vazio com o campo think; o gpt-oss esgotava "
         "num_predict=400 no raciocínio.", "think só para famílias de raciocínio; num_predict 1024; "
         "with_fallbacks repete sem think e com o dobro do orçamento.",
         "Vazio virava nota 0 por falha de transporte, não de qualidade."),
        ("Instrução de formato cara", f"get_format_instructions() gerava {te['format_instructions_pydantic']} "
         "tokens por extração.", f"Instrução compacta gerada do mesmo schema ({te['format_instructions_compacto']} "
         "tokens); parse e validação seguem no PydanticOutputParser.", "Mesma garantia, menos contexto."),
        ("Régua de pontuação com falso acerto", "O termo \"h\" casava com qualquer texto; listas sem ponto "
         "contavam como 1 frase.", "pontuacao.py v1.1: termo curto como palavra isolada, itens de lista "
         "contados; todas as colunas reexecutadas.", "Mudar a régua exige remedir todos os lados."),
        ("Legado sem credencial de nuvem", "O código de ai/ foi escrito para o Ollama local e não envia "
         "Authorization.", "Adaptador troca só o transporte (proxy do requests e host/modelo da instância); "
         "nenhum arquivo de ai/ alterado.", "Preservar o grupo de controle."),
        ("Falso positivo de escopo", "\"Traduz ... 'state of charge'\" era bloqueado: o léxico do domínio não "
         "tinha termos em inglês.", "Termos EN adicionados; conjunto de regressão com 44 perguntas legítimas.",
         "Bloquear demais também é defeito e é medido."),
    ]
    e.append(_tabela([["Problema", "Causa", "Solução", "Por quê"]] + [list(p) for p in probs],
                     [3.0 * cm, 4.6 * cm, 5.2 * cm, L - 12.8 * cm], st))

    # 5 ------------------------------------------------------------------
    e.append(H("5. Equipe e divisão de trabalho"))
    eq = json.loads((RAIZ / "docs" / "equipe.json").read_text(encoding="utf-8"))
    e.append(_tabela([["Nome", "RM", "Tarefa principal"]] +
                     [[i["nome"], i["rm"], i["tarefa_principal"]] for i in eq["integrantes"]],
                     [4.5 * cm, 2.2 * cm, L - 6.7 * cm], st))
    e.append(Spacer(1, 4))
    e.append(P("Reprodução: <i>pip install -r requirements-sprint3.txt</i>, configurar <i>.env</i> a partir de "
               "<i>.env.example</i>, <i>python -m evals.executar_tudo</i>. Todos os números deste relatório "
               "são rastreáveis até os JSONs em <i>evals/resultados/</i> e o consolidado <i>evals/sprint3_results.json</i>."))
    doc.build(e)
    return destino
