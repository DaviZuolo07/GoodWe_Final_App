"""
Moderação — prompt injection, jailbreak e extração de prompt.

Complementa o `scope_validator`: aquele decide SOBRE O QUE se pode falar; este
decide se a mensagem está tentando reescrever as regras do sistema.

POR QUE ANTES DO MODELO
-----------------------
Uma instrução maliciosa que chega ao modelo já venceu metade da batalha: a
partir dali, a defesa depende de o modelo escolher obedecer o system prompt em
vez da mensagem. Às vezes escolhe, às vezes não — e "às vezes" não é postura de
segurança. Detectando antes, a instrução nunca é lida.

O QUE ISTO NÃO É
----------------
Isto não substitui o prompt: um atacante criativo escreve o que nenhum regex
prevê. É uma camada, não uma garantia. A defesa real é a soma das três:
detecção determinística aqui, instrução no system prompt (v1/v2), e o fato de
o assistente simplesmente não ter acesso a dados de terceiros para vazar.

Escrever isso no relatório vale mais que fingir cobertura total.
"""

import re
from dataclasses import dataclass

from src.guardrails.scope_validator import normalizar

# ---------------------------------------------------------------------------
# 1. Sobrescrita de instrução
# ---------------------------------------------------------------------------
SOBRESCRITA = [
    r"\bignor\w*\b.{0,30}\b(instruc\w*|regras|orientac\w*|prompt|comandos|anterior\w*)\b",
    r"\b(esqueca|desconsidere|apague|anule|descarte)\b.{0,30}"
    r"\b(instruc\w*|regras|prompt|contexto|tudo)\b",
    r"\ba partir de agora voce (e|sera|vai ser)\b",
    r"\bde agora em diante voce\b",
    r"\bvoce (nao |)tem mais\b.{0,25}\b(restric\w*|regras|limites)\b",
    r"\bsem (nenhuma |qualquer |)(restric\w*|censura|limite|filtro)\b",
    r"\bnovas instruc\w*\b", r"\bsobrescrev\w*\b.{0,20}\bregras\b",
    r"\bmodo (desenvolvedor|dev|debug|admin|deus|livre|irrestrito)\b",
    r"\bdevmode\b", r"\bdan\b(?!\w)", r"\bjailbreak\b",
]

# ---------------------------------------------------------------------------
# 2. Extração do prompt
# ---------------------------------------------------------------------------
EXTRACAO = [
    r"\b(qual|mostre|revele|exiba|imprima|repita|copie|liste)\b.{0,40}"
    r"\b(system prompt|prompt do sistema|suas instruc\w*|suas regras|"
    r"seu prompt|prompt inicial|configurac\w* inicial)\b",
    r"\bsystem prompt\b.{0,25}\b(completo|inteiro|na integra|literal)\b",
    r"\brepita\b.{0,25}\b(tudo|acima|o texto)\b.{0,25}\bantes\b",
    r"\bquais (sao |)(as |)suas (regras|instruc\w*|diretrizes)\b",
    r"\bo que (esta |foi )escrito\b.{0,25}\b(antes|acima|no seu)\b",
]

# ---------------------------------------------------------------------------
# 3. Troca de identidade / persona por texto
# ---------------------------------------------------------------------------
# O papel vem do sistema autenticado, nunca da mensagem. Afirmar um papel na
# conversa para obter dado de terceiro é escalação de privilégio — o ataque
# mais provável num sistema multi-persona e o mais fácil de passar batido.
IDENTIDADE = [
    r"\b(sou|eu sou|aqui e)\b.{0,15}\b(o |a |)(sindic\w*|administrador\w*|"
    r"operador\w*|tecnic\w*|zelador\w*|gerente|dono|proprietari\w*)\b",
    r"\bfinja que (voce |eu |)\b", r"\bfaca de conta que\b",
    r"\bfinja ser\b", r"\bassuma o papel\b", r"\bincorpor\w*\b.{0,20}\bpersonagem\b",
    r"\bvoce agora e\b", r"\bcomo se voce fosse\b",
    r"\bautorizad\w* pel\w*\b.{0,25}\b(sindic|administrac|goodwe)\b",
]

# ---------------------------------------------------------------------------
# 4. Injeção indireta: pedido malicioso embrulhado em tarefa inofensiva
# ---------------------------------------------------------------------------
INDIRETA = [
    r"\b(traduza|traduzir|converta)\b.{0,80}\b(execute|obedeca|siga|cumpra|"
    r"faca o que|aplique)\b",
    r"\b(roteiro|filme|cena|historia|conto|ficcao|romance|livro)\b.{0,80}"
    r"\b(burlar|contornar|fraudar|hackear|adulterar|sem restric\w*|"
    r"ignorar as regras)\b",
    r"\b(hipoteticamente|em teoria|se voce pudesse|imagine que)\b.{0,60}"
    r"\b(sem (as |)regras|ignorar|burlar|revelar)\b",
    r"\bpara fins (educacionais|academicos|de pesquisa)\b.{0,50}"
    r"\b(burlar|contornar|fraudar|adulterar)\b",
    r"\bresponda (em |)(base64|rot13|codigo|cifra)\b",
]

# ---------------------------------------------------------------------------
# 5. Fraude operacional
# ---------------------------------------------------------------------------
FRAUDE = [
    r"\b(burlar|contornar|fraudar|adulterar|manipular|enganar|driblar)\b.{0,40}"
    r"\b(medic\w*|medidor|cobranca|faturamento|leitura|consumo|sistema|tarifa)\b",
    r"\b(nao pagar|deixar de pagar|carregar de graca|energia gratis)\b",
    r"\bacesso\b.{0,25}\b(sem autorizac\w*|indevido|de outro)\b",
]

CATEGORIAS = {
    "sobrescrita_de_instrucao": SOBRESCRITA,
    "extracao_de_prompt": EXTRACAO,
    "troca_de_identidade": IDENTIDADE,
    "injecao_indireta": INDIRETA,
    "fraude_operacional": FRAUDE,
}


@dataclass(frozen=True)
class Deteccao:
    seguro: bool
    categoria: str = "ok"
    padrao: str = ""

    @property
    def bloqueado(self) -> bool:
        return not self.seguro


def analisar(mensagem: str) -> Deteccao:
    """Pré-check de moderação. Roda antes de qualquer chamada ao modelo."""
    texto = normalizar(mensagem)
    for categoria, padroes in CATEGORIAS.items():
        for p in padroes:
            if re.search(p, texto):
                return Deteccao(False, categoria, p)
    return Deteccao(True)


def resposta_de_recusa(d: Deteccao) -> str:
    """
    Recusa curta e sem eco.

    Duas regras deliberadas: não repetir o texto do usuário (evita que a
    injeção apareça na resposta) e não explicar QUAL padrão disparou (isso
    ensinaria a contorná-lo na tentativa seguinte).
    """
    if d.categoria == "troca_de_identidade":
        return ("Seu perfil de acesso vem do sistema, não da conversa, então não "
                "posso atender pedidos baseados em outro papel. Posso ajudar com "
                "recarga, consumo e uso dos carregadores.")
    if d.categoria == "extracao_de_prompt":
        return ("Não compartilho minhas instruções internas. Posso ajudar com "
                "dúvidas sobre recarga de veículos elétricos no condomínio.")
    if d.categoria == "fraude_operacional":
        return ("Não posso ajudar com isso. Posso explicar como o consumo é medido "
                "e como a tarifa é calculada, se for útil.")
    return ("Não posso atender esse pedido. Sigo como assistente de recarga da "
            "GoodWe — posso ajudar com carregadores, consumo e tempo de recarga.")


def verificar_resposta(resposta: str) -> tuple:
    """
    Pós-check: a resposta vazou o prompt do sistema?

    Procura marcadores estruturais do nosso próprio prompt. Se aparecerem, algo
    passou pelo pré-check e o conteúdo não pode sair.
    """
    texto = normalizar(resposta)
    marcadores = [
        "# identidade", "# escopo", "# limites de dominio", "# personas",
        "esta identidade e fixa", "regras de conteudo",
        "system prompt", "minhas instrucoes sao",
    ]
    for m in marcadores:
        if m in texto:
            return False, f"possivel vazamento de prompt: {m!r}"
    return True, ""
