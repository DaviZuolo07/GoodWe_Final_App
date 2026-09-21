"""
Guardrail de ENTRADA — moderação (prompt injection, jailbreak, abuso).

Roda ANTES de qualquer chamada ao LLM. Se bloquear, o modelo nem é chamado:
custo zero, latência de microssegundos, resposta idêntica em toda execução.

Por que regras determinísticas e não "perguntar ao LLM se é ataque":
  1. Um classificador LLM é, ele mesmo, suscetível a injection.
  2. Recusa de segurança precisa ser auditável ("por que bloqueou?" -> a
     regra X casou com o trecho Y). Ver `ResultadoModeracao.gatilhos`.
  3. O prompt v2 continua sendo a SEGUNDA camada (defesa em profundidade,
     OWASP Top 10 for LLM Applications 2025 — LLM01 Prompt Injection).

Limite honesto: regras não pegam paráfrase criativa infinita. Por isso o
prompt v2 isola a entrada em <pergunta_usuario> (spotlighting, Hines et al.,
2024, arXiv:2403.14720) e a saída passa pelo validador de `scope_validator`.

Técnicas de evasão tratadas na normalização:
  - acentos/maiúsculas         "IGNORE", "instruções"
  - caracteres invisíveis      zero-width space entre letras
  - letras espaçadas           "i g n o r e"
  - leetspeak                  "1gn0r3", "r3v3l3"
  - payload em base64          "aWdub3JlIHN1YXMgcmVncmFz"
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Normalização
# --------------------------------------------------------------------------- #
_INVISIVEIS = re.compile(r"[\u200b-\u200f\u2060-\u2064\ufeff\u00ad]")
_LETRAS_ESPACADAS = re.compile(r"\b(?:[a-z]\s){3,}[a-z]\b")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                       "7": "t", "@": "a", "$": "s", "!": "i"})
_BASE64 = re.compile(r"(?:[A-Za-z0-9+/]{4}){5,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")


def normalizar(texto: str) -> str:
    """NFKC -> sem invisíveis -> minúsculas -> sem acento -> espaços colapsados."""
    t = unicodedata.normalize("NFKC", texto or "")
    t = _INVISIVEIS.sub("", t).lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _variantes(texto: str) -> list[str]:
    """Texto normalizado + versão sem letras espaçadas + versão sem leetspeak."""
    base = normalizar(texto)
    colado = _LETRAS_ESPACADAS.sub(lambda m: m.group(0).replace(" ", ""), base)
    leet = colado.translate(_LEET)
    return list(dict.fromkeys([base, colado, leet]))


def _decodificar_base64(texto: str) -> list[str]:
    achados = []
    for trecho in _BASE64.findall(texto or ""):
        try:
            bruto = base64.b64decode(trecho, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if sum(c.isprintable() for c in bruto) / max(len(bruto), 1) > 0.9:
            achados.append(bruto)
    return achados


# --------------------------------------------------------------------------- #
# Regras (sobre texto normalizado: minúsculo e sem acento)
# --------------------------------------------------------------------------- #
_ALVOS_INSTRUCAO = r"(instruc\w*|regras?|orientac\w*|diretrizes?|prompt|comandos?|restric\w*|politicas?|limites?|configurac\w*)"

REGRAS: dict[str, list[tuple[str, str]]] = {
    "prompt_injection": [
        ("ignorar_regras",
         rf"\b(ignor\w*|desconsider\w*|esquec\w*|esquece\w*|descart\w*|anul\w*|sobrescrev\w*|desobedec\w*)\b.{{0,40}}\b{_ALVOS_INSTRUCAO}"),
        ("ignorar_regras_en",
         r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(instructions?|rules?|prompt|guidelines|system|policy)"),
        ("revelar_prompt",
         r"\b(revel\w*|mostr\w*|exib\w*|imprim\w*|repit\w*|diga|conte|copie|vaz\w*|cole|liste|reveal|show|print|repeat|leak|dump)\b"
         r".{0,50}\b(system ?prompt|prompt (do|de) sistema|seu prompt|suas instruc\w*|instruc\w* (inicia|origina|intern|ocult|secret)\w*"
         r"|regras (internas|ocultas|secretas)|configurac\w* (interna|oculta)|your (instructions|prompt))"),
        ("mencao_system_prompt", r"\b(system ?prompt|prompt (do|de) sistema)\b"),
        ("delimitador_injetado",
         r"</?\s*(pergunta_usuario|system|sistema|regras\w*|identidade|canario|instruc\w*|assistant)\s*>"
         r"|\[/?inst\]|<\|(im_start|im_end|start|end|system)\|>|#{2,}\s*(system|sistema)\b"),
        ("traduzir_e_executar",
         r"\b(traduz\w*|translate|decodifi\w*|decode)\b.{0,160}\b(execut\w*|obedec\w*|cumpr\w*|aplique|siga|seguir|run|execute|follow|obey)\b"),
    ],
    "jailbreak": [
        ("troca_de_identidade",
         r"\b(a partir de agora|de agora em diante|daqui pra frente|from now on)\b.{0,60}"
         r"\b(voce e|voce sera|voce vai ser|seja|atue|aja|comporte|you are|act as|be)\b"),
        ("modo_irrestrito",
         r"\b(dev ?mode|modo (desenvolvedor|dev|deus|irrestrito|livre|sem (filtro|restric\w*))|developer mode|jailbreak"
         r"|do anything now|\bdan\b|sem (nenhuma |qualquer )?(restric\w*|filtros?|censura|limites)|without (any )?restrictions|unfiltered|uncensored)"),
        ("roleplay_de_ia",
         r"\b(finja|fingir|finge|imagine|roleplay|role play|interprete|encene|pretend|vamos (brincar|fingir)|roteiro|personagem)\b"
         r".{0,80}\b(ia|inteligencia artificial|assistente|chatbot|bot|modelo de linguagem|ai)\b"),
        ("confirmacao_de_modo", r"\bconfirm\w* (dizendo|com|escrevendo)\b.{0,30}\b(ativ\w*|liberad\w*|on)\b"),
    ],
    "dados_de_terceiros": [
        ("dados_de_outra_unidade",
         r"\b(historic\w*|saldo|dados|sessoes|recargas|consumo|cpf|placa|telefone|e-?mail|senha|cadastro|extrato|fatura)\b"
         r".{0,40}\b(do|da|de|dos|das)\s+(apartamento|apto|ap|unidade|bloco|morador\w*|vizinh\w*|outros?|todos)\b"),
        ("unidade_especifica_com_dado",
         r"\b(apartamento|apto|unidade)\s*\d+.{0,40}\b(saldo|historic\w*|consumo|recargas|dados|fatura|extrato)\b"),
        ("alegacao_de_papel",
         r"\b(eu sou|sou|falo como|aqui e|sendo)\s+(o |a )?(sindic\w*|administrador\w*|admin|operador\w*|zelador\w*|gerente|desenvolvedor\w*|suporte|dono do sistema)\b"
         r".{0,80}\b(mostre|me de|libere|acesse|exib\w*|list\w*|quero ver|preciso ver|abra)\b"),
    ],
    "conduta_indevida": [
        ("fraude_medicao",
         r"\b(burl\w*|fraud\w*|adulter\w*|manipul\w*|contorn\w*|engan\w*|dribl\w*|hacke\w*|bypass|desativ\w*)\b"
         r".{0,50}\b(medi\w*|medidor\w*|cobranc\w*|tarifa\w*|pagamento\w*|consumo|leitura|contador|rfid|cartao|autentic\w*|protec\w*|\bdr\b|diferencial|aterramento)"),
        ("fraude_medicao_inversa",
         r"\b(medic\w*|medidor\w*|cobranc\w*|leitura)\b.{0,30}\b(burl\w*|fraud\w*|adulter\w*|engan\w*)"),
        ("furto_de_energia",
         r"\b(gato de energia|fazer (um )?gato|furt\w* (de )?energia|roub\w* (de )?energia|carregar (de gra[cç]a|sem pagar))"),
    ],
}

_COMPILADAS = {cat: [(nome, re.compile(p)) for nome, p in regras] for cat, regras in REGRAS.items()}

# --------------------------------------------------------------------------- #
# Respostas fixas (curtas, sem ecoar o pedido, sem lição de moral)
# --------------------------------------------------------------------------- #
RESPOSTAS = {
    "prompt_injection": (
        "Não posso atender esse pedido. Sigo como assistente de recarga de veículos elétricos "
        "da GoodWe e posso ajudar com tempo e custo de recarga, uso dos carregadores ou regras do condomínio."
    ),
    "jailbreak": (
        "Não posso atender esse pedido. Sigo como assistente de recarga de veículos elétricos "
        "da GoodWe e posso ajudar com tempo e custo de recarga, uso dos carregadores ou regras do condomínio."
    ),
    "dados_de_terceiros": (
        "Não posso acessar nem exibir dados de outros moradores ou unidades, e o seu perfil é definido "
        "pelo sistema, não pela mensagem. Para relatórios de uso do condomínio, use o painel "
        "administrativo com o seu login ou fale com a administração."
    ),
    "conduta_indevida": (
        "Não posso ajudar com isso, nem em cenário fictício. Se houver suspeita de erro na medição ou "
        "na cobrança, registre a ocorrência com a administração do condomínio para verificação técnica."
    ),
}

ORDEM = ("conduta_indevida", "dados_de_terceiros", "prompt_injection", "jailbreak")


@dataclass
class ResultadoModeracao:
    bloqueado: bool
    categoria: str | None = None
    gatilhos: list[str] = field(default_factory=list)
    resposta: str | None = None


def moderar(texto: str, _profundidade: int = 0) -> ResultadoModeracao:
    variantes = _variantes(texto)
    achados: dict[str, list[str]] = {}
    for categoria, regras in _COMPILADAS.items():
        for nome, rx in regras:
            if any(rx.search(v) for v in variantes):
                achados.setdefault(categoria, []).append(nome)

    # Payload escondido em base64: decodifica e modera o conteúdo.
    if _profundidade == 0:
        for decodificado in _decodificar_base64(texto):
            interno = moderar(decodificado, _profundidade=1)
            if interno.bloqueado:
                achados.setdefault("prompt_injection", []).append(
                    f"base64->{interno.categoria}")

    for categoria in ORDEM:
        if categoria in achados:
            return ResultadoModeracao(True, categoria, achados[categoria], RESPOSTAS[categoria])
    return ResultadoModeracao(False)
