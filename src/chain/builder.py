"""
Núcleo conversacional da Sprint 03, reconstruído em LCEL.

    Sprint 2 (manual)                       Sprint 3 (LCEL)
    ------------------------------------    ------------------------------------------
    lista de dicts montada à mão            ChatPromptTemplate versionado (prompts/)
    requests.post + data["message"]         ChatOllama | StrOutputParser
    histórico cresce sem limite             RunnableWithMessageHistory +
                                            ConversationTokenBufferMemory (teto fixo)
    modelo faz a conta de cabeça            PydanticOutputParser(ConsultaRecarga) ->
                                            calculadora determinística
    escopo "na boa vontade" do prompt       guardrails de entrada e de saída

PIPELINE DE UM TURNO (tudo Runnable, composto com `|`):

    entrada ─► moderação ─► RunnableBranch ─┬─ bloqueado/recusa ─► resposta fixa
                                            └─ segue ─► extração estruturada (Pydantic)
                                                        ─► cálculo determinístico
                                                        ─► [prompt | llm | parser] + memória
                                                        ─► validação de saída

Uso rápido:
    from src.chain.builder import ChatbotChargeOps
    bot = ChatbotChargeOps()                      # prompt v2, gpt-oss:120b
    r = bot.responder("Minha bateria é de 60 kWh", session_id="ana")
    print(r.texto)
"""

from __future__ import annotations

import os
import re
import uuid
import warnings
from dataclasses import dataclass, field

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (Runnable, RunnableBranch, RunnableConfig,
                                      RunnableLambda, RunnablePassthrough)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import ValidationError

from src.chain import prompts, tokens
from src.chain.llm import get_llm, get_llm_robusto
from src.chain.memoria import MAX_TOKENS_PADRAO, RepositorioSessoes, renderizar_fatos
from src.dominio import recarga
from src.guardrails.moderation import moderar
from src.guardrails.scope_validator import validar_escopo, validar_saida
from src.schemas.consulta_recarga import ConsultaRecarga, instrucoes_compactas, mesclar_fatos
from src.schemas.resultados import RespostaTurno

# --------------------------------------------------------------------------- #
# Telemetria de um turno (vai para o eval: tokens, chamadas, rota)
# --------------------------------------------------------------------------- #
@dataclass
class Telemetria:
    chamadas_llm: int = 0
    tokens_prompt: int = 0
    tokens_resposta: int = 0
    prompts_enviados: list[str] = field(default_factory=list)
    uso: UsageMetadataCallbackHandler = field(default_factory=UsageMetadataCallbackHandler)

    def tokens_servidor(self) -> tuple[int, int]:
        entrada = sum(u.get("input_tokens", 0) for u in self.uso.usage_metadata.values())
        saida = sum(u.get("output_tokens", 0) for u in self.uso.usage_metadata.values())
        return entrada, saida


def _telemetria(config: RunnableConfig | None) -> Telemetria | None:
    return ((config or {}).get("configurable") or {}).get("telemetria")


def _registrar_prompt(valor: ChatPromptValue, config: RunnableConfig) -> ChatPromptValue:
    """Passo transparente entre prompt e LLM: mede exatamente o que é enviado."""
    tel = _telemetria(config)
    if tel is not None:
        msgs = valor.to_messages()
        tel.chamadas_llm += 1
        tel.tokens_prompt += tokens.contar_mensagens(msgs)
        tel.prompts_enviados.append("\n".join(f"[{m.type}] {m.content}" for m in msgs))
    return valor


def _registrar_resposta(texto: str, config: RunnableConfig) -> str:
    tel = _telemetria(config)
    if tel is not None:
        tel.tokens_resposta += tokens.contar(texto)
    return texto


_RE_LATEX = re.compile(r"\\\(|\\\)|\\\[|\\\]|\\(text|mathrm)\{([^}]*)\}|\\(times|cdot)|\\approx|\\frac")


def limpar_saida(texto: str) -> str:
    """Remove resíduos de LaTeX e cabeçalhos markdown (o prompt proíbe; aqui é a garantia)."""
    t = _RE_LATEX.sub(lambda m: m.group(2) or {"\\times": "×", "\\cdot": "×"}.get(m.group(0), " "), texto or "")
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# --------------------------------------------------------------------------- #
# Chain 1 — resposta ao usuário:  prompt | llm | parser
# --------------------------------------------------------------------------- #
def montar_chain_resposta(versao: str, llm) -> Runnable:
    return (
        prompts.montar_template(versao)
        | RunnableLambda(_registrar_prompt, name="registrar_prompt")
        | llm
        | StrOutputParser()
        | RunnableLambda(limpar_saida, name="limpar_saida")
        | RunnableLambda(_registrar_resposta, name="registrar_resposta")
    )


# --------------------------------------------------------------------------- #
# Chain 2 — extração estruturada:  prompt | llm(format=json) | PydanticOutputParser
# --------------------------------------------------------------------------- #
PROMPT_EXTRACAO = """Você extrai parâmetros de recarga de veículo elétrico de uma conversa em português do Brasil.
Responda SOMENTE com um objeto JSON válido, sem markdown e sem texto antes ou depois.

<regras>
1. Preencha um campo apenas se o usuário o informou na mensagem atual ou no histórico. Caso contrário, use null.
2. Nunca estime, complete ou invente valores. Tarifa e preços só se o usuário disser o número.
3. Percentuais como número de 0 a 100. "Carga completa", "encher" ou "até 100" significam soc_alvo_pct = 100.
4. potencia_carregador_kw é a potência do carregador; potencia_max_ac_veiculo_kw é o limite do carro em AC.
5. Se a mensagem atual mudar um valor (por exemplo, um novo nível desejado), use o valor novo.
6. intencao descreve a mensagem atual.
</regras>

<formato>
{format_instructions}
</formato>"""

HUMANO_EXTRACAO = """<historico>
{historico_texto}
</historico>

<mensagem_atual>
{pergunta}
</mensagem_atual>
{correcao}"""


FORMATO_EXTRACAO = os.getenv("EXTRACAO_FORMATO", "compacto")   # compacto | pydantic


def montar_chain_extracao(llm_json, formato: str = FORMATO_EXTRACAO) -> tuple[Runnable, PydanticOutputParser]:
    parser = PydanticOutputParser(pydantic_object=ConsultaRecarga)
    instrucoes = (parser.get_format_instructions() if formato == "pydantic"
                  else instrucoes_compactas(ConsultaRecarga))
    template = ChatPromptTemplate.from_messages([
        ("system", PROMPT_EXTRACAO),
        ("human", HUMANO_EXTRACAO),
    ]).partial(format_instructions=instrucoes)
    chain = (template
             | RunnableLambda(_registrar_prompt, name="registrar_prompt_extracao")
             | llm_json
             | parser)
    return chain, parser


# Gatilho barato para decidir se vale a chamada de extração (economiza 1
# chamada de LLM em perguntas conceituais como "o que é OCPP?").
GATILHO_EXTRACAO = re.compile(
    r"\d|quanto tempo|demora|quanto (custa|pago|vou pagar|fica|sai|gasta)|custo|tarifa|valor|"
    r"kwh|\bkw\b|bateria|carga|carregar at|livre|dispon|ocupad|falha|offline|estado d",
    re.I,
)
INTENCOES_DE_CALCULO = ("estimativa_tempo", "estimativa_custo")


def _perfil_para_fatos(perfil: dict | None) -> dict:
    """Dados cadastrais que entram como fatos-base do cálculo (o perfil é verdade)."""
    if not perfil:
        return {}
    mapa = {"capacidade_bateria_kwh": "capacidade_bateria_kwh", "battery_kwh": "capacidade_bateria_kwh",
            "potencia_carregador_kw": "potencia_carregador_kw", "charger_kw": "potencia_carregador_kw",
            "potencia_max_ac_veiculo_kw": "potencia_max_ac_veiculo_kw"}
    fatos = {}
    for origem, destino in mapa.items():
        if perfil.get(origem) not in (None, ""):
            fatos[destino] = perfil[origem]
    return fatos


def renderizar_perfil(perfil: dict | None, persona: str) -> str:
    linhas = [f"- papel: {persona} (definido pelo sistema)"]
    rotulos = {"nome": "nome", "veiculo": "veículo", "capacidade_bateria_kwh": "bateria (kWh)",
               "potencia_carregador_kw": "carregador (kW)", "potencia_max_ac_veiculo_kw":
               "limite AC do veículo (kW)", "bloco": "bloco", "apartamento": "apartamento"}
    for chave, rotulo in rotulos.items():
        if perfil and perfil.get(chave) not in (None, ""):
            linhas.append(f"- {rotulo}: {str(perfil[chave]).replace('.', ',')}")
    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# O chatbot
# --------------------------------------------------------------------------- #
class ChatbotChargeOps:
    def __init__(
        self,
        versao_prompt: str = prompts.VERSAO_PADRAO,
        papel: str = "principal",
        model: str | None = None,
        guardrails: bool = True,
        max_tokens_memoria: int = MAX_TOKENS_PADRAO,
        llm_resposta: BaseChatModel | None = None,
        llm_extracao: BaseChatModel | None = None,
        llm_contador: BaseChatModel | None = None,
    ):
        self.versao = versao_prompt
        self.prompt = prompts.carregar(versao_prompt)
        self.guardrails = guardrails
        self.modelos_base = prompts.modelos_na_base()

        # LLMs (injetáveis — os testes offline passam modelos falsos)
        self.llm_resposta = llm_resposta or get_llm_robusto("redator", papel=papel, model=model)
        self.llm_extracao = llm_extracao or get_llm_robusto(
            "estruturado", papel=papel, model=model, format="json")
        contador = llm_contador or llm_resposta or get_llm("classificador", papel=papel, model=model)

        # Memória por sessão
        self.sessoes = RepositorioSessoes(contador, max_tokens_memoria)

        # Chains
        self.chain_resposta = montar_chain_resposta(versao_prompt, self.llm_resposta)
        with warnings.catch_warnings():
            # Marcado como deprecated no LangChain 1.x em favor da persistência do
            # LangGraph, que pertence aos Módulos 3/4. O escopo exige esta classe.
            warnings.simplefilter("ignore")
            self.chain_com_memoria = RunnableWithMessageHistory(
                self.chain_resposta,
                self.sessoes.historico,
                input_messages_key="pergunta",
                history_messages_key="historico",
            )
        self.chain_extracao, self.parser_extracao = montar_chain_extracao(self.llm_extracao)
        self.usa_calculo = self.prompt.usa("calculo_verificado")

        self.pipeline = self._montar_pipeline()

    # ------------------------------------------------------------------ #
    def _montar_pipeline(self):
        moderacao = RunnableLambda(self._etapa_guardrails, name="guardrails_entrada")
        bloqueio = RunnableLambda(self._etapa_resposta_fixa, name="resposta_fixa")
        fluxo_llm = (
            RunnablePassthrough.assign(estruturado=RunnableLambda(self._etapa_extracao, name="extracao"))
            | RunnablePassthrough.assign(contexto=RunnableLambda(self._etapa_contexto, name="contexto"))
            | RunnableLambda(self._etapa_llm, name="resposta_llm")
            | RunnableLambda(self._etapa_validar_saida, name="guardrail_saida")
        )
        return moderacao | RunnableBranch((lambda x: x["guardrail"] is not None, bloqueio), fluxo_llm)

    # -- etapa 1: guardrails de entrada ---------------------------------
    def _etapa_guardrails(self, x: dict) -> dict:
        if not self.guardrails:
            return {**x, "guardrail": None}
        m = moderar(x["pergunta"])
        if m.bloqueado:
            return {**x, "guardrail": {"rota": "bloqueio_moderacao", "categoria": m.categoria,
                                       "gatilhos": m.gatilhos, "resposta": m.resposta}}
        e = validar_escopo(x["pergunta"], self.modelos_base)
        if not e.permitido:
            return {**x, "guardrail": {"rota": "recusa_escopo", "categoria": e.categoria,
                                       "gatilhos": e.gatilhos, "resposta": e.resposta}}
        return {**x, "guardrail": None}

    def _etapa_resposta_fixa(self, x: dict) -> RespostaTurno:
        # Turno bloqueado NÃO entra na memória: evita que uma injeção fique
        # "morando" no histórico e seja reenviada ao modelo nos turnos seguintes.
        g = x["guardrail"]
        return RespostaTurno(texto=g["resposta"], rota=g["rota"], categoria_guardrail=g["categoria"])

    # -- etapa 2: extração estruturada (Pydantic) -------------------------
    def _etapa_extracao(self, x: dict, config: RunnableConfig) -> dict:
        resultado = {"acionada": False, "valido": None, "tentativas": 0,
                     "consulta": None, "erro": None}
        if not self.usa_calculo or not GATILHO_EXTRACAO.search(x["pergunta"]):
            return resultado

        sessao = self.sessoes.obter(config["configurable"]["session_id"])
        janela = sessao.historico.messages[-6:]
        historico_texto = "\n".join(f"{'usuário' if m.type == 'human' else 'assistente'}: {m.content}"
                                    for m in janela) or "(vazio)"
        entrada = {"pergunta": x["pergunta"], "historico_texto": historico_texto, "correcao": ""}
        resultado["acionada"] = True

        for tentativa in (1, 2):
            resultado["tentativas"] = tentativa
            try:
                consulta: ConsultaRecarga = self.chain_extracao.invoke(entrada, config=config)
                resultado.update(valido=tentativa == 1, consulta=consulta, erro=None)
                if tentativa == 2:
                    resultado["valido_apos_correcao"] = True
                break
            except (OutputParserException, ValidationError, ValueError) as e:
                resultado.update(valido=False, erro=f"{type(e).__name__}: {str(e)[:240]}")
                # Autocorreção: devolve o erro ao modelo uma única vez.
                entrada["correcao"] = (f"\n<erro_anterior>Seu JSON anterior foi rejeitado pela validação: "
                                       f"{str(e)[:300]}. Corrija e responda só o JSON.</erro_anterior>")
            except Exception as e:  # rede, timeout: não derruba o turno
                resultado.update(valido=False, erro=f"{type(e).__name__}: {str(e)[:200]}")
                break
        return resultado

    # -- etapa 3: contexto (fatos da sessão + cálculo verificado) ---------
    def _etapa_contexto(self, x: dict, config: RunnableConfig) -> dict:
        sessao = self.sessoes.obter(config["configurable"]["session_id"])
        est = x["estruturado"]
        consulta: ConsultaRecarga | None = est.get("consulta")

        if consulta is not None:
            sessao.fatos = mesclar_fatos(sessao.fatos, consulta.fatos())

        calculo = None
        texto_calculo = "nenhum cálculo necessário nesta mensagem"
        if consulta is not None and consulta.intencao in INTENCOES_DE_CALCULO:
            base = mesclar_fatos(_perfil_para_fatos(x.get("perfil")), sessao.fatos)
            if consulta.intencao == "estimativa_custo" and "tarifa_kwh_brl" not in base:
                base["tarifa_kwh_brl"] = prompts.base_produtos()["tarifa_condominio_brl_kwh"]
            try:
                completa = ConsultaRecarga(intencao=consulta.intencao, **base)
                calculo = recarga.calcular(completa)
                texto_calculo = recarga.renderizar(calculo, completa)
                if (consulta.intencao == "estimativa_custo" and "tarifa_kwh_brl" not in sessao.fatos
                        and calculo.status == "ok"):
                    texto_calculo += "\n(tarifa usada: a cadastrada do condomínio)"
            except ValidationError:
                texto_calculo = ("os percentuais informados são inconsistentes; peça ao usuário para "
                                 "confirmar o nível atual e o desejado")
        elif consulta is not None and consulta.intencao == "faturamento":
            e_kwh = consulta.energia_entregue_kwh or sessao.fatos.get("energia_entregue_kwh")
            tarifa = consulta.tarifa_kwh_brl or sessao.fatos.get("tarifa_kwh_brl")
            if e_kwh and tarifa:
                texto_calculo = (f"custo da energia informada: {e_kwh:g} kWh x R$ {tarifa:.2f} = "
                                 f"R$ {e_kwh * tarifa:.2f}").replace(".", ",")
        elif est.get("acionada") and consulta is None:
            texto_calculo = ("não foi possível interpretar os números da mensagem; se for um cálculo, "
                             "peça ao usuário para confirmar os dados")

        return {
            "perfil_usuario": renderizar_perfil(x.get("perfil"), x.get("persona", "morador")),
            "fatos_sessao": renderizar_fatos(sessao.fatos),
            "calculo_verificado": texto_calculo,
            "calculo": calculo.model_dump() if calculo else None,
        }

    # -- etapa 4: resposta com memória --------------------------------------
    def _etapa_llm(self, x: dict, config: RunnableConfig) -> RespostaTurno:
        ctx = x["contexto"]
        texto = self.chain_com_memoria.invoke(
            {"pergunta": x["pergunta"], "perfil_usuario": ctx["perfil_usuario"],
             "fatos_sessao": ctx["fatos_sessao"], "calculo_verificado": ctx["calculo_verificado"]},
            config=config,
        )
        sessao = self.sessoes.obter(config["configurable"]["session_id"])
        sessao.turnos += 1
        est = x["estruturado"]
        return RespostaTurno(
            texto=texto, rota="llm",
            consulta=est["consulta"].model_dump() if est.get("consulta") else None,
            estruturado_valido=est["valido"] if est.get("acionada") else None,
            estruturado_tentativas=est.get("tentativas", 0),
            calculo=ctx.get("calculo"),
        )

    # -- etapa 5: guardrail de saída ---------------------------------------
    def _etapa_validar_saida(self, r: RespostaTurno) -> RespostaTurno:
        if not self.guardrails:
            return r
        texto, motivo = validar_saida(r.texto, prompts.CANARIO)
        if motivo:
            return r.model_copy(update={"texto": texto, "saida_corrigida_por_guardrail": motivo})
        return r

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def responder(self, pergunta: str, session_id: str | None = None,
                  persona: str = "morador", perfil: dict | None = None) -> RespostaTurno:
        tel = Telemetria()
        config: RunnableConfig = {
            "configurable": {"session_id": session_id or uuid.uuid4().hex, "telemetria": tel},
            "callbacks": [tel.uso],
            "run_name": f"chargeops_{self.versao}",
        }
        r: RespostaTurno = self.pipeline.invoke(
            {"pergunta": pergunta, "persona": persona, "perfil": perfil}, config=config)
        entrada, saida = tel.tokens_servidor()
        return r.model_copy(update={
            "chamadas_llm": tel.chamadas_llm,
            "tokens_prompt": tel.tokens_prompt,
            "tokens_resposta": tel.tokens_resposta,
            "tokens_servidor_entrada": entrada,
            "tokens_servidor_saida": saida,
            "prompt_enviado": "\n\n=====\n\n".join(tel.prompts_enviados),
        })

    def extrair(self, pergunta: str) -> ConsultaRecarga:
        """Modo 'extrair' da Aula 03: só a chain estruturada, sem memória."""
        return self.chain_extracao.invoke(
            {"pergunta": pergunta, "historico_texto": "(vazio)", "correcao": ""})

    def memoria(self, session_id: str) -> dict:
        s = self.sessoes.obter(session_id)
        return {
            "mensagens_na_janela": len(s.historico.messages),
            "tokens_na_janela": s.historico.tokens_na_janela(),
            "max_token_limit": s.historico.max_token_limit,
            "eventos_de_poda": s.historico.eventos_de_poda,
            "mensagens_descartadas": len(s.historico.mensagens_descartadas),
            "fatos_da_sessao": s.fatos,
        }
