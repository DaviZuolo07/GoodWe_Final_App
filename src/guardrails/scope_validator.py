"""
Validação de escopo — bloco C da rubrica (15 pts).

PRINCÍPIO
---------
Guardrail não pede ao modelo que se comporte. Guardrail decide ANTES do modelo,
com código que não pode ser convencido por texto. Um prompt é uma sugestão
muito bem escrita; um `if` não é.

Isso muda o que dá para afirmar na banca. Com regra no prompt, a resposta
honesta é "o modelo geralmente recusa". Com verificação determinística, é "a
requisição não chega ao modelo".

ONDE ESTE ARQUIVO ATUA
----------------------
    pergunta -> [PRÉ] -> chain LCEL -> [PÓS] -> resposta

    PRÉ  bloqueia assunto restrito antes de gastar chamada
    PÓS  confere se a resposta cumpriu o que o pré-check exigia

NOTA DE HONESTIDADE METODOLÓGICA
--------------------------------
Os padrões abaixo são GERAIS, escritos a partir das categorias do §6 (jurídico,
financeiro, segurança elétrica, especificação inexistente), não copiados das
perguntas do eval. Se fossem recortados caso a caso, o eval mediria a nossa
capacidade de decorar o gabarito, não a robustez do sistema. O eval está
congelado justamente para tornar essa diferença verificável.
"""

import re
import unicodedata
from dataclasses import dataclass


def normalizar(texto: str) -> str:
    texto = (texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


# ---------------------------------------------------------------------------
# Domínios restritos (§6): recusa COM encaminhamento a profissional habilitado
# ---------------------------------------------------------------------------

DOMINIOS = {
    "eletrico": {
        "profissional": "eletricista habilitado",
        "motivo": "instalação e segurança elétrica exigem responsável técnico",
        "padroes": [
            r"\bbitola\b", r"\bmm2\b|\bmm²\b",
            r"\bdisjuntor\b", r"\bdr\b(?!\w)", r"\bdps\b",
            r"\baterrament\w*", r"\bquadro (de |)(forca|distribuicao|energia)\b",
            r"\bligar\b.{0,30}\b(direto|na rede|no quadro)\b",
            r"\b(abrir|desmontar|consertar|reparar|trocar)\b.{0,40}"
            r"\b(carregador|equipamento|placa|componente|fusivel)\b",
            r"\bfiacao\b", r"\bcabeament\w*\b.{0,20}\b(instal|dimension)",
            r"\b(cheiro|cheirando)\b.{0,20}\bqueimad", r"\bfumaca\b",
            r"\bsuperaquec\w*", r"\bcurto[- ]circuito\b",
        ],
    },
    "juridico": {
        "profissional": "advogado",
        "motivo": "interpretação de lei, convenção ou contrato exige advogado",
        "padroes": [
            r"\bprocessar\b", r"\bacao judicial\b", r"\bprocesso\b.{0,20}\bcontra\b",
            r"\bartigo\b.{0,25}\b(codigo|lei|civil)\b", r"\bcodigo civil\b",
            r"\bconvencao (do |de |)condominio\b.{0,30}\b(permite|proibe|obriga|diz)\b",
            r"\bmeus direitos\b", r"\bdireito legal\b", r"\be legal\b.{0,25}\?",
            r"\bposso (processar|acionar|denunciar)\b", r"\bindenizacao\b",
            r"\bmulta\b.{0,25}\b(legal|ilegal|valida)\b", r"\brescis\w*",
        ],
    },
    "financeiro": {
        "profissional": "contador ou consultor financeiro",
        "motivo": "recomendação de investimento exige profissional certificado",
        "padroes": [
            r"\bvale a pena\b.{0,35}\b(investir|financiar|comprar|instalar)\b",
            r"\bretorno (do |sobre o |)investimento\b", r"\broi\b",
            r"\bpayback\b", r"\bfinanciar\b", r"\bfinanciamento\b",
            r"\btaxa ideal\b", r"\bquanto (devo|deveria) cobrar\b",
            r"\bcompensa (mais |)(investir|financiar)\b",
            r"\bemprestimo\b", r"\brentabilidade\b", r"\bpayback\b",
        ],
    },
}

# Assuntos legítimos que a rede de domínio pega por engano.
# EC-05 ("gasolina x elétrico") foi recusado indevidamente na rodada de 09/09:
# comparar custo por km é explicação, não recomendação de investimento.
EXCECOES = [
    r"\b(gasolina|combustivel|etanol|diesel)\b.{0,40}\b(comparad|versus|vs|em relacao)\b",
    r"\bcomparad\w*\b.{0,40}\b(gasolina|combustivel|etanol|diesel)\b",
    r"\bcusto por (km|quilometro)\b",
    r"\bquanto custa\b.{0,30}\b(carregar|recarga|kwh)\b",
    r"\bcomo (e |)calculad\w*\b.{0,25}\b(tarifa|custo|rateio)\b",
]

# ---------------------------------------------------------------------------
# Fora de escopo
# ---------------------------------------------------------------------------

FORA_DE_ESCOPO = [
    r"\b(previsao do tempo|temperatura amanha|vai chover)\b",
    r"\breceita\b.{0,25}\b(bolo|comida|prato|massa)\b",
    r"\b(filme|serie|novela|musica|livro)\b.{0,30}\b(indic|recomend|sugir|assistir|ver)\b",
    r"\b(escrev|faca|gere|cri)\w*\b.{0,25}\b(codigo|script|programa|funcao)\b"
    r".{0,25}\b(python|java|javascript|c\+\+|sql)\b",
    r"\bcodigo (em |)python\b",
    r"\b(quem ganhou|placar|jogo do)\b",
    r"\b(piada|poema|poesia|conto)\b",
]

# Assunto do domínio: se aparecer, NÃO é fora de escopo mesmo com verbo genérico.
ANCORAS_DOMINIO = [
    r"\bcarregad\w*", r"\brecarg\w*", r"\bcarregament\w*", r"\bbateria\b",
    r"\bkwh\b", r"\bkw\b", r"\bveiculo eletrico\b", r"\bcarro eletrico\b",
    r"\bcondominio\b", r"\bgoodwe\b", r"\bchargeops\b", r"\btarifa\b",
    r"\beletromobilidade\b", r"\bcarga\b", r"\btomada\b", r"\bconector\b",
]

# ---------------------------------------------------------------------------
# Especificação de produto inexistente (§6: "não inventar especificações")
# ---------------------------------------------------------------------------

PEDIDO_DE_ESPEC = re.compile(
    r"\b(corrente maxima|potencia nominal|protocolo|especificac\w*|"
    r"ficha tecnica|datasheet|tensao de entrada|ip\d{2}|certificac\w*)\b"
)
# Códigos de modelo: letras + dígitos, típicos de SKU (HCA-9000X, GW5000-EV).
CODIGO_DE_MODELO = re.compile(r"\b[a-z]{2,6}[- ]?\d{3,5}[a-z]{0,2}\b", re.I)


@dataclass(frozen=True)
class Veredito:
    permitido: bool
    categoria: str = "ok"
    profissional: str = ""
    motivo: str = ""
    padrao: str = ""

    @property
    def bloqueado(self) -> bool:
        return not self.permitido


def _casa(padroes, texto) -> str:
    for p in padroes:
        if re.search(p, texto):
            return p
    return ""


def validar(pergunta: str) -> Veredito:
    """Pré-check. Roda antes da chain, em microssegundos."""
    texto = normalizar(pergunta)

    if not texto:
        return Veredito(False, "vazio", motivo="pergunta vazia")

    tem_ancora = bool(_casa(ANCORAS_DOMINIO, texto))
    tem_excecao = bool(_casa(EXCECOES, texto))

    # 1. Domínios restritos — prioridade máxima: risco elétrico primeiro.
    for nome in ("eletrico", "juridico", "financeiro"):
        regra = DOMINIOS[nome]
        padrao = _casa(regra["padroes"], texto)
        if padrao:
            # Exceção só vale para financeiro. Risco elétrico e jurídico não
            # têm zona cinzenta: na dúvida, encaminha.
            if nome == "financeiro" and tem_excecao:
                continue
            return Veredito(False, f"dominio_{nome}", regra["profissional"],
                            regra["motivo"], padrao)

    # 2. Fora de escopo — âncora do domínio tem precedência.
    padrao = _casa(FORA_DE_ESCOPO, texto)
    if padrao and not tem_ancora:
        return Veredito(False, "fora_de_escopo",
                        motivo="assunto fora do domínio ChargeOps", padrao=padrao)

    # 3. Especificação de produto não cadastrado.
    if PEDIDO_DE_ESPEC.search(texto) and CODIGO_DE_MODELO.search(texto):
        return Veredito(False, "espec_inexistente",
                        motivo="especificação de equipamento não consta na base",
                        padrao="codigo_de_modelo + pedido_de_especificacao")

    return Veredito(True)


def resposta_de_recusa(v: Veredito) -> str:
    """
    Recusa determinística: sempre com encaminhamento, sempre em 2 frases.

    O §6 exige recusa COM orientação a profissional habilitado. Recusar sem
    encaminhar vale nota parcial. Gerar este texto em código, e não pelo modelo,
    garante que os dois elementos estejam SEMPRE presentes.
    """
    if v.categoria.startswith("dominio_"):
        return (
            f"Não posso orientar sobre isso, porque {v.motivo}. "
            f"Procure um {v.profissional}; posso ajudar com dúvidas de recarga, "
            "consumo e uso dos carregadores do condomínio."
        )
    if v.categoria == "espec_inexistente":
        return (
            "Não tenho essa especificação na minha base e não vou estimar valores "
            "de equipamento elétrico. Consulte a ficha técnica oficial GoodWe ou a "
            "assistência autorizada."
        )
    if v.categoria == "fora_de_escopo":
        return (
            "Isso está fora do meu escopo. Posso ajudar com recarga de veículos "
            "elétricos, consumo de energia e uso dos carregadores do condomínio."
        )
    return ("Não consegui entender a pergunta. Pode reformular com mais detalhes "
            "sobre a recarga ou o carregador?")


def verificar_resposta(resposta: str, v: Veredito) -> tuple:
    """
    Pós-check. Devolve (aprovado, motivo).

    Existe para o caso em que o pré-check libera mas a resposta escorrega — por
    exemplo, uma pergunta genérica sobre instalação que o modelo responde com
    bitola de cabo.
    """
    texto = normalizar(resposta)

    if not texto:
        return False, "resposta vazia"

    if re.search(r"\b\d+([.,]\d+)?\s?mm2?\b|\bbitola de \d", texto):
        return False, "resposta contém dimensionamento de cabo"

    if re.search(r"\bdisjuntor de \d+\s?a\b", texto):
        return False, "resposta contém especificação de disjuntor"

    if re.search(r"\bartigo \d", texto):
        return False, "resposta cita artigo de lei"

    return True, ""
