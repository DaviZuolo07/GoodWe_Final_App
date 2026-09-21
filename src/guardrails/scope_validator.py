"""
Guardrail de ESCOPO (§6 do contrato) — entrada e saída.

ENTRADA (`validar_escopo`), em ordem de prioridade:
  1. emergencia_eletrica     cheiro de queimado, fumaça, faísca, choque
  2. seguranca_eletrica      instalação, cabos, disjuntor, abrir/consertar equipamento
  3. juridico                processar, advogado, lei, Código Civil
  4. financeiro              investimento, retorno, financiamento, taxa
  5. especificacao_fora_da_base   modelo de produto que NÃO está em prompts/base_produtos.json
  6. fora_de_escopo          assunto sem nenhum termo do domínio + padrão típico de off-topic

As recusas de domínio restrito são respostas fixas COM encaminhamento a
profissional habilitado, como o §6 exige. Uma recusa determinística nunca
"esquece" de encaminhar; uma recusa gerada por LLM às vezes esquece.

O critério de fora de escopo é conservador de propósito: só bloqueia quando
NÃO há nenhum termo do domínio. Pergunta vaga como "quanto tempo" passa (é um
edge case legítimo e o LLM pede os dados). Bloquear demais é defeito também —
o eval mede isso ("recusou_pergunta_legitima").

SAÍDA (`validar_saida`): última barreira depois do LLM.
  - canário do prompt na resposta        -> vazamento de prompt
  - tags internas do prompt na resposta  -> vazamento de prompt
  - bitola/seção de cabo/corrente de disjuntor -> instrução elétrica perigosa
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.guardrails.moderation import RESPOSTAS as RESPOSTAS_MODERACAO
from src.guardrails.moderation import normalizar

# --------------------------------------------------------------------------- #
# Vocabulário do domínio (texto normalizado)
# --------------------------------------------------------------------------- #
TERMOS_DOMINIO = re.compile(
    r"\b(carro\w*|veicul\w*|ve|ves|eletric\w*|recarg\w*|recarreg\w*|carreg\w*|bateri\w*|kwh|kw|"
    r"wallbox|tomada\w*|conector\w*|tipo ?2|ccs\d?|chademo|ocpp|modbus|telemetri\w*|soc|autonomia|"
    r"goodwe|chargeops|chargegrid|condomini\w*|sindic\w*|morador\w*|vaga\w*|garage\w*|fila\w*|"
    r"sess\w*|tarifa\w*|energia|potencia|corrente|tensao|volt\w*|amper\w*|inversor\w*|solar|"
    r"fotovoltaic\w*|hibrid\w*|plug-?in|byd|tesla|dolphin|volvo|bmw|gwm|ora|kwid|leaf|ioniq|"
    r"km|quilometr\w*|abastec\w*|combustivel|gasolina|etanol|mobilidade|eletroposto\w*|"
    r"state of charge|charg\w*|battery|ev|evse|wall ?box|plug)\b"
)

PADROES_FORA_DE_ESCOPO = re.compile(
    r"\b(previsao do tempo|vai chover|chuva|clima (em|de|amanha|hoje)|temperatura (em|amanha|hoje) (em|no|na)|"
    r"receita\w* (de|do|da|para)|bolo|cozinh\w*|culinari\w*|"
    r"codigo|python|javascript|java|html|css|sql|programa(r|cao)|script|algoritmo|ordena\w* (uma )?lista|"
    r"filme\w*|serie\w*|musica\w*|cancao|livro\w*|novela|jogo\w*|futebol|campeonato|copa do mundo|time de|"
    r"politic\w*|eleic\w*|president\w*|piada\w*|poema\w*|poesia|horoscopo|signo\w*|"
    r"capital d[aoe]|quem (ganhou|descobriu|inventou)|traduz\w*|redac\w*|dever de casa|equac\w*)\b"
)

# --------------------------------------------------------------------------- #
# Domínios restritos (§6)
# --------------------------------------------------------------------------- #
EMERGENCIA = re.compile(
    r"\b(cheir\w* (a|de) queimad\w*|queimad\w*|fumac\w*|faisc\w*|fogo|incendi\w*|chamas?|"
    r"(levei|tomei|deu|dando) (um )?choque|choque eletrico|esquent\w* (muito|demais)|superaquec\w*|derret\w*|estal\w*)\b"
)
SEGURANCA_ELETRICA = re.compile(
    r"\b(bitola|secao (do|de) (cabo|fio)|mm2|mm²|disjuntor\w*|\bdps\b|\bdr\b|diferencial residual|aterrament\w*|"
    r"quadro (de forca|de distribuicao|eletrico|geral|de luz)|ligar (direto|diretamente) (no|na|ao)|"
    r"instal\w* (o|um|meu|minha|nosso|do|de|uma)? ?(carregador|wallbox|tomada|ponto de recarga)|"
    r"fiac\w*|emend\w*|extens\w*|benjamim|filtro de linha|adaptador de tomada|"
    r"abr\w* (o|a) (carregador|equipamento|tampa|wallbox)|abrir e (trocar|consertar)|"
    r"trocar (o|a) (componente|placa|fusivel|rele|contator)|consert\w*|reparar|desmont\w*)\b"
)
JURIDICO = re.compile(
    r"\b(process\w* (o|a|os|as) (condominio|sindic\w*|administrador\w*|administracao|empresa|goodwe|vizinh\w*)|"
    r"advogad\w*|acao judicial|justica|juiz\w*|tribunal|codigo civil|codigo de defesa|\bcdc\b|artigo \d|lei \d|lei n|"
    r"jurisprud\w*|meus direitos|direito (de|do|meu)|ilegal|legalmente|e legal|multad\w*|clausula\w*|"
    r"indeniz\w*|danos morais|notificac\w* extrajudicial|entrar na justica|judicial\w*)\b"
)
FINANCEIRO = re.compile(
    r"\b(retorno (do|sobre o|de) investimento|\broi\b|payback|vale a pena (investir|financiar)|investir|investiment\w*|"
    r"financi\w*|emprestim\w*|taxa (de juros|ideal|interna|de retorno|minima)|\btir\b|\bvpl\b|valuation|"
    r"acoes da|bolsa de valores|renda fixa|tesouro direto|cripto\w*|aplicac\w* financeira)\b"
)

INTENCAO_ESPEC = re.compile(
    r"\b(corrente|protocolo|especificac\w*|datasheet|ficha tecnica|potencia|tensao|conector|"
    r"compativel|suporta|consumo|eficiencia|grau de protecao|ip\d\d|garantia|preco|dimens\w*)\b"
)
CODIGO_MODELO = re.compile(r"\b([a-z]{2,6}\d{0,2}-?\d{2,5}[a-z0-9-]*|[a-z]{2,4}\d{1,3}k?-[a-z0-9-]{2,10})\b")
CODIGOS_IGNORADOS = re.compile(r"^(ccs\d*|iec\d*|nbr\d*|iso\d*|ocpp\d*|tipo\d*|type\d*|ip\d+|nr\d+|co\d+|abnt\d*|sae\d*|gb\d*)$")

# --------------------------------------------------------------------------- #
# Respostas fixas com encaminhamento a profissional habilitado
# --------------------------------------------------------------------------- #
RESPOSTAS = {
    "emergencia_eletrica": (
        "Pare de usar o carregador agora: se puder fazer isso com segurança, interrompa a recarga pelo "
        "aplicativo ou desligue o circuito no quadro, sem tocar em partes aquecidas. Não abra o equipamento "
        "nem tente reparar; acione a assistência técnica autorizada GoodWe e a administração do condomínio. "
        "Se houver fumaça ou fogo, afaste-se e ligue 193 (Corpo de Bombeiros)."
    ),
    "seguranca_eletrica": (
        "Não posso orientar instalação, dimensionamento de cabos, proteções ou reparos elétricos. Isso exige "
        "projeto e execução por eletricista habilitado, conforme as normas ABNT NBR 5410 e NBR 17019, com "
        "ART (CREA) ou TRT (CFT) emitida pelo profissional responsável. Posso explicar potência, tempo de "
        "recarga e o uso do carregador."
    ),
    "juridico": (
        "Não posso dar orientação jurídica sobre esse caso. Procure um advogado ou a Defensoria Pública, "
        "levando a convenção, o regimento interno do condomínio e as comunicações com o síndico. Posso "
        "explicar como funciona o uso compartilhado dos carregadores, se ajudar."
    ),
    "financeiro": (
        "Não posso fazer recomendação financeira nem calcular retorno de investimento ou taxas para o "
        "condomínio. Essa análise deve ser feita por um contador ou consultor financeiro, considerando o custo "
        "dos equipamentos e da instalação, a adequação da entrada de energia, a tarifa cobrada por kWh e a "
        "demanda esperada de uso. Posso explicar como funciona o faturamento por kWh, se ajudar."
    ),
    "fora_de_escopo": (
        "Isso está fora do meu escopo. Sou o assistente de recarga de veículos elétricos da GoodWe e posso "
        "ajudar com tempo e custo de recarga, uso dos carregadores e regras do condomínio."
    ),
}


def _resposta_especificacao(modelo: str) -> str:
    seguro = re.sub(r"[^A-Za-z0-9-]", "", modelo)[:30].upper() or "citado"
    return (f"Não possuo a especificação do modelo {seguro} na minha base, então não vou estimar "
            "valores técnicos dele. Consulte o datasheet oficial da GoodWe ou a assistência técnica "
            "autorizada.")


@dataclass
class ResultadoEscopo:
    permitido: bool
    categoria: str = "em_escopo"
    gatilhos: list[str] = field(default_factory=list)
    resposta: str | None = None


def _modelo_fora_da_base(texto_norm: str, modelos_base: set[str]) -> str | None:
    if not INTENCAO_ESPEC.search(texto_norm):
        return None
    if not re.search(r"\b(goodwe|modelo|carregador|wallbox|inversor)\b", texto_norm):
        return None
    base_norm = {normalizar(m) for m in modelos_base}
    for codigo in CODIGO_MODELO.findall(texto_norm):
        if CODIGOS_IGNORADOS.match(codigo.replace("-", "")) or re.fullmatch(r"\d+(kw|kwh|v|a)?", codigo):
            continue
        if not any(codigo in m for m in base_norm):
            return codigo
    return None


def validar_escopo(texto: str, modelos_base: set[str] | None = None) -> ResultadoEscopo:
    t = normalizar(texto)

    for categoria, regra in (("emergencia_eletrica", EMERGENCIA),
                             ("seguranca_eletrica", SEGURANCA_ELETRICA),
                             ("juridico", JURIDICO),
                             ("financeiro", FINANCEIRO)):
        achado = regra.search(t)
        if achado:
            return ResultadoEscopo(False, categoria, [achado.group(0)], RESPOSTAS[categoria])

    if modelos_base is not None:
        modelo = _modelo_fora_da_base(t, modelos_base)
        if modelo:
            return ResultadoEscopo(False, "especificacao_fora_da_base", [modelo],
                                   _resposta_especificacao(modelo))

    fora = PADROES_FORA_DE_ESCOPO.search(t)
    if fora and not TERMOS_DOMINIO.search(t):
        return ResultadoEscopo(False, "fora_de_escopo", [fora.group(0)], RESPOSTAS["fora_de_escopo"])

    return ResultadoEscopo(True)


# --------------------------------------------------------------------------- #
# Saída
# --------------------------------------------------------------------------- #
TAGS_INTERNAS = re.compile(
    r"</?(identidade|escopo|regras_seguranca|regras_calculo|formato|canario|base_produtos|"
    r"perfil_usuario|fatos_da_sessao|calculo_verificado|exemplos?)>", re.I)
INSTRUCAO_ELETRICA = re.compile(
    r"\b\d+([.,]\d+)?\s?mm(2|²)|\bbitola\b[^.]{0,30}\d|\bdisjuntor (de )?\d+\s?a\b|\bcabo de \d+([.,]\d+)?\s?mm", re.I)


def validar_saida(texto: str, canario: str | None = None) -> tuple[str, str | None]:
    """Devolve (texto_final, motivo_da_correcao | None)."""
    if canario and canario.lower() in (texto or "").lower():
        return RESPOSTAS_MODERACAO["prompt_injection"], "vazamento_canario"
    if TAGS_INTERNAS.search(texto or ""):
        return RESPOSTAS_MODERACAO["prompt_injection"], "vazamento_tags_prompt"
    if INSTRUCAO_ELETRICA.search(texto or ""):
        return RESPOSTAS["seguranca_eletrica"], "instrucao_eletrica_na_saida"
    return texto, None
