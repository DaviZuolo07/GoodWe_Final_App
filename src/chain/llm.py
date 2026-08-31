"""
Fábrica de LLMs da Sprint 3.

Único lugar do projeto que sabe COMO falar com o modelo. Todo o resto
(`builder.py`, guardrails, grafo, eval) recebe um objeto pronto e não faz ideia
se ele é gpt-oss, qwen ou kimi.

Isso não é preciosismo de arquitetura. O bloco B da rubrica exige comparar dois
ou mais modelos com os parâmetros documentados, e o bônus de +1 ponto pede
chamada multi-provider. Se o modelo estivesse instanciado dentro da chain, cada
comparação viraria um copy-paste. Aqui vira um argumento:

    from src.chain.llm import get_llm
    principal  = get_llm()                      # gpt-oss:120b
    comparacao = get_llm(papel="comparacao")    # o segundo modelo
"""

import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# ---------------------------------------------------------------------------
# Perfis de parâmetros
# ---------------------------------------------------------------------------
# Cada perfil é uma decisão registrada, não um número solto no código. Quando o
# §6 pedir "documente temperature, top_p e max_tokens", a resposta é este
# dicionário — e o porquê está no comentário de cada linha.

PERFIS = {
    # Classificação de intenção: precisa ser reprodutível. A mesma pergunta tem
    # que cair na mesma intenção sempre, senão o eval não mede nada, mede sorte.
    "classificador": {"temperature": 0.0, "top_p": 1.0, "num_predict": 160},

    # Redação para o usuário: um pouco de variação deixa o texto menos robótico
    # sem soltar a mão do modelo. Acima de ~0.4 ele começa a florear número.
    "redator": {"temperature": 0.2, "top_p": 0.9, "num_predict": 400},

    # Saída estruturada (Pydantic): zero criatividade. Queremos JSON válido no
    # primeiro try, não uma interpretação artística do schema.
    "estruturado": {"temperature": 0.0, "top_p": 1.0, "num_predict": 500},
}

PERFIL_PADRAO = "redator"

# ---------------------------------------------------------------------------
# Registro de modelos
# ---------------------------------------------------------------------------
# `papel` é a função no experimento, não o nome do modelo. Assim o eval e o
# relatório falam em "principal x comparacao" e trocar de modelo é editar o
# .env, sem tocar em código nenhum.

PAPEIS_MODELO = {
    "principal":  ("OLLAMA_MODEL",   "gpt-oss:120b"),
    "comparacao": ("OLLAMA_MODEL_B", ""),
    "extra":      ("OLLAMA_MODEL_C", ""),
}

MODELOS = tuple(PAPEIS_MODELO)


class ModeloNaoConfigurado(RuntimeError):
    """Papel pedido mas sem modelo definido no .env."""


def _limpo(nome_var: str, padrao: str = "") -> str:
    """
    Lê do ambiente já sem espaço, quebra de linha e aspas.

    Chave colada do navegador vem com \\n no fim mais vezes do que se imagina,
    e o 401 resultante parece problema de credencial quando é de string.
    """
    return (os.getenv(nome_var) or padrao).strip().strip('"').strip("'")


def nome_do_modelo(papel: str = "principal") -> str:
    if papel not in PAPEIS_MODELO:
        raise ValueError(f"papel desconhecido: {papel!r}. Use um de {MODELOS}")

    variavel, padrao = PAPEIS_MODELO[papel]
    nome = _limpo(variavel, padrao)

    if not nome:
        raise ModeloNaoConfigurado(
            f"O papel '{papel}' não tem modelo definido: falta {variavel} no .env.\n"
            "Rode 'python -m src.teste_auth' para ver os modelos que a sua "
            "chave enxerga e escolha um."
        )
    return nome


def get_llm(
    perfil: str = PERFIL_PADRAO,
    papel: str = "principal",
    model: str | None = None,
    reasoning: str | bool | None = None,
    **sobrescritas,
) -> ChatOllama:
    """
    perfil     temperature/top_p/num_predict (ver PERFIS)
    papel      qual modelo do experimento: principal | comparacao | extra
    model      nome explícito, ignora o papel (uso pontual)
    reasoning  'low' | 'medium' | 'high' | False -> vira o campo `think`.
               gpt-oss e kimi são modelos de raciocínio: sem limitar isso, eles
               "pensam" por segundos antes de escrever três frases.
    """
    if perfil not in PERFIS:
        raise ValueError(f"perfil desconhecido: {perfil!r}. Use um de {list(PERFIS)}")

    parametros = {**PERFIS[perfil], **sobrescritas}

    model = model or nome_do_modelo(papel)
    base_url = _limpo("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    api_key = _limpo("OLLAMA_API_KEY")

    if reasoning is None:
        bruto = _limpo("OLLAMA_THINK", "low").lower()
        reasoning = False if bruto in ("", "none", "false", "0") else bruto

    na_nuvem = "ollama.com" in base_url

    if na_nuvem and not api_key:
        raise RuntimeError(
            "OLLAMA_HOST aponta para a nuvem mas OLLAMA_API_KEY está vazia.\n"
            "Crie a chave em https://ollama.com/settings/keys"
        )

    if na_nuvem and model.endswith("-cloud"):
        # O sufixo '-cloud' serve para o Ollama LOCAL puxar um modelo da nuvem.
        # Falando direto com ollama.com, o nome correto é sem sufixo — e o
        # servidor devolve 404, fácil de confundir com problema de credencial.
        model = model[: -len("-cloud")]

    kwargs = {
        "model": model,
        "base_url": base_url,
        "reasoning": reasoning,
        # Não valida o modelo na construção: a fábrica é chamada em import de
        # módulo e não pode derrubar a aplicação porque o servidor demorou a
        # responder. Quem valida é o src/diagnostico.py, de propósito.
        "validate_model_on_init": False,
        **parametros,
    }

    if na_nuvem:
        kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {api_key}"}}

    return ChatOllama(**kwargs)


def descrever(perfil: str = PERFIL_PADRAO, papel: str = "principal") -> dict:
    """Parâmetros efetivos — para o relatório e o cabeçalho de cada eval."""
    base_url = _limpo("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        modelo = nome_do_modelo(papel)
    except ModeloNaoConfigurado:
        modelo = "(nao configurado)"

    return {
        "papel": papel,
        "model": modelo,
        "host": base_url,
        "modo": "nuvem" if "ollama.com" in base_url else "local",
        "perfil": perfil,
        "think": _limpo("OLLAMA_THINK", "low").lower() or "none",
        **PERFIS[perfil],
    }


def modelos_configurados() -> dict:
    """{papel: nome} apenas dos papéis realmente preenchidos no .env."""
    saida = {}
    for papel in MODELOS:
        try:
            saida[papel] = nome_do_modelo(papel)
        except ModeloNaoConfigurado:
            continue
    return saida