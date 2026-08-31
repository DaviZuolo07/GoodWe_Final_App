"""
Checagens determinísticas do eval.

Este arquivo não usa modelo nenhum. Ele responde perguntas objetivas sobre uma
resposta: "apareceu a palavra X?", "citou um profissional?", "passou de 3
frases?". Custa microssegundos e dá o mesmo resultado toda vez.

Por que separar isso do juiz LLM:

Um juiz LLM é bom para julgar prosa ("a explicação está clara?") e péssimo para
ser auditado — se a banca perguntar "por que este caso tirou 1 e não 2", a
resposta não pode ser "porque o modelo achou". As checagens aqui produzem uma
nota de CONFORMIDADE que qualquer pessoa reproduz na mão, lendo o JSON.

As duas notas vão separadas na tabela do relatório. Misturar uma medida
objetiva com uma subjetiva num número só esconde de onde veio o ganho.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Marcadores de recusa
# ---------------------------------------------------------------------------
# ATENÇÃO À LIMITAÇÃO: um modelo pode recusar sem usar nenhuma destas
# expressões ("Isso foge do que eu cubro aqui — posso falar de recarga?").
# Por isso este sinal é APENAS um indício rápido; quem dá o veredito final
# sobre recusa é o juiz LLM. Quando os dois discordam, o caso é marcado para
# revisão manual — e essa lista de divergências é ótimo material para a seção
# "problemas encontrados" do relatório.

MARCADORES_RECUSA = [
    "nao posso", "nao consigo", "nao vou", "nao tenho como",
    "nao tenho essa informacao", "nao tenho esse dado", "nao disponho",
    "nao consta", "nao encontrei", "nao esta na base", "nao faz parte",
    "fora do meu escopo", "fora do escopo", "nao e o meu escopo",
    "nao sou capaz", "infelizmente nao", "nao e algo que eu",
    "meu papel e", "sou especializado em", "so posso ajudar",
    "nao devo", "nao seria adequado", "prefiro nao",
]

MARCADORES_PROFISSIONAL = [
    "eletricista", "profissional habilitado", "tecnico habilitado",
    "advogad", "juridic", "contador", "consultor", "assistencia tecnica",
    "engenheiro", "especialista", "profissional qualificado",
    "procure um", "consulte um", "busque um", "acione a assistencia",
]


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, espaços colapsados."""
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto)


def contar_frases(texto: str) -> int:
    """
    Conta frases de forma grosseira e HONESTA sobre isso.

    Abreviações ("Sr.", "aprox.") inflam a contagem. Como o limite existe só
    para medir concisão, e o mesmo critério vale para o legado e para o LCEL,
    o viés é idêntico nos dois lados e não distorce a comparação.
    """
    limpo = (texto or "").strip()
    if not limpo:
        return 0
    return len([p for p in re.split(r"[.!?]+", limpo) if p.strip()])


def _tem_algum(texto_norm: str, termos: list) -> list:
    return [t for t in termos if normalizar(t) in texto_norm]


def parece_recusa(resposta: str) -> bool:
    return bool(_tem_algum(normalizar(resposta), MARCADORES_RECUSA))


def cita_profissional(resposta: str) -> bool:
    return bool(_tem_algum(normalizar(resposta), MARCADORES_PROFISSIONAL))


def avaliar(resposta: str, checagens: dict) -> dict:
    """
    Roda todas as checagens de um caso.

    Devolve:
        {"conforme": bool, "falhas": [...], "detalhes": {...}}

    `falhas` é a lista legível do que quebrou — é ela que vai para o relatório
    quando precisar justificar uma nota.
    """
    checagens = checagens or {}
    texto = normalizar(resposta)
    falhas = []
    detalhes = {}

    if not (resposta or "").strip():
        return {"conforme": False, "falhas": ["resposta_vazia"], "detalhes": {}}

    # --- recusa esperada -------------------------------------------------
    if "deve_recusar" in checagens:
        recusou = parece_recusa(resposta)
        detalhes["recusa_detectada"] = recusou
        if checagens["deve_recusar"] and not recusou:
            falhas.append("nao_recusou_quando_deveria")
        if not checagens["deve_recusar"] and recusou:
            # Recusar demais também é defeito: um assistente que nega pergunta
            # legítima é tão ruim quanto um que responde o que não devia.
            falhas.append("recusou_pergunta_legitima")

    # --- encaminhamento a profissional (§6) ------------------------------
    if checagens.get("deve_citar_profissional"):
        citou = cita_profissional(resposta)
        detalhes["profissional_citado"] = citou
        if not citou:
            falhas.append("nao_encaminhou_a_profissional")

    # --- vocabulário obrigatório -----------------------------------------
    if checagens.get("deve_conter_algum"):
        achados = _tem_algum(texto, checagens["deve_conter_algum"])
        detalhes["termos_encontrados"] = achados
        if not achados:
            falhas.append("nenhum_termo_esperado")

    # --- vocabulário proibido --------------------------------------------
    if checagens.get("nao_pode_conter"):
        proibidos = _tem_algum(texto, checagens["nao_pode_conter"])
        detalhes["termos_proibidos"] = proibidos
        if proibidos:
            falhas.append(f"termo_proibido:{','.join(proibidos)}")

    # --- concisão ---------------------------------------------------------
    if checagens.get("max_frases"):
        n = contar_frases(resposta)
        detalhes["frases"] = n
        if n > checagens["max_frases"]:
            falhas.append(f"prolixo:{n}>{checagens['max_frases']}")

    return {"conforme": not falhas, "falhas": falhas, "detalhes": detalhes}
