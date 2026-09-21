"""
Fábrica de LLMs da Sprint 3.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_ollama import ChatOllama

from src.chain import tokens

load_dotenv()

# ---------------------------------------------------------------------------
# Perfis de parâmetros (§6: documentar temperature, top_p e max_tokens)
# ---------------------------------------------------------------------------
# `num_predict` é o max_tokens do Ollama.
#
# ATENÇÃO — modelos de raciocínio: no Ollama o `num_predict` limita o total
# gerado, INCLUINDO os tokens de raciocínio (canal "analysis" do gpt-oss). Com
# 400 tokens e think=low, parte das respostas saía vazia ou cortada: o
# orçamento acabava no raciocínio. Por isso o teto subiu e a concisão passou a
# ser controlada pelo PROMPT (<formato>), não pelo corte bruto de tokens.
#
# `seed` fixa a amostragem para o eval ser reexecutável. Em servidor
# compartilhado (nuvem) a reprodutibilidade é "melhor esforço", não garantia.

PERFIS = {
    # Classificação/roteamento: precisa ser reprodutível.
    "classificador": {"temperature": 0.0, "top_p": 1.0, "num_predict": 512, "seed": 42},

    # Redação para o usuário: um pouco de variação deixa o texto menos robótico
    # sem soltar a mão do modelo. Acima de ~0.4 ele começa a florear número.
    "redator": {"temperature": 0.2, "top_p": 0.9, "num_predict": 1024, "seed": 42},

    # Saída estruturada (Pydantic): zero criatividade, JSON válido no 1º try.
    "estruturado": {"temperature": 0.0, "top_p": 1.0, "num_predict": 1024, "seed": 42},
}

PERFIL_PADRAO = "redator"

# Modelos que aceitam o campo `think`. Para os demais o campo NÃO é enviado:
# gemma4 e glm-*-flash devolvem conteúdo vazio quando recebem `think`.
PREFIXOS_RACIOCINIO = ("gpt-oss", "kimi", "deepseek", "qwen3", "nemotron")

# `papel` é a função no experimento, não o nome do modelo.
PAPEIS_MODELO = {
    "principal":  ("OLLAMA_MODEL",   "gpt-oss:120b"),
    "comparacao": ("OLLAMA_MODEL_B", ""),
    "extra":      ("OLLAMA_MODEL_C", ""),
}

MODELOS = tuple(PAPEIS_MODELO)

OMITIR = "omitir"   # sentinela: não enviar o campo `think`


class ModeloNaoConfigurado(RuntimeError):
    """Papel pedido mas sem modelo definido no .env."""


class RespostaVazia(RuntimeError):
    """O modelo respondeu 200 com conteúdo vazio (orçamento gasto no raciocínio)."""


def _limpo(nome_var: str, padrao: str = "") -> str:
    """Lê do ambiente sem espaço, quebra de linha e aspas (chave colada do navegador)."""
    return (os.getenv(nome_var) or padrao).strip().strip('"').strip("'")


def nome_do_modelo(papel: str = "principal") -> str:
    if papel not in PAPEIS_MODELO:
        raise ValueError(f"papel desconhecido: {papel!r}. Use um de {MODELOS}")
    variavel, padrao = PAPEIS_MODELO[papel]
    nome = _limpo(variavel, padrao)
    if not nome:
        raise ModeloNaoConfigurado(
            f"O papel '{papel}' não tem modelo definido: falta {variavel} no .env.\n"
            "Rode 'python -m src.teste_auth' para ver os modelos que a sua chave enxerga."
        )
    return nome


def resolver_provedor(model: str) -> tuple[str, str, str]:
    """
    'local:qwen3:8b'      -> ('local', 'http://127.0.0.1:11434', 'qwen3:8b')
    'nuvem:gpt-oss:20b'   -> ('nuvem', 'https://ollama.com',     'gpt-oss:20b')
    'gpt-oss:120b'        -> provedor padrão do OLLAMA_HOST
    """
    host_padrao = _limpo("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    host_local = _limpo("OLLAMA_HOST_LOCAL", "http://127.0.0.1:11434").rstrip("/")

    if model.startswith("local:"):
        return "local", host_local, model[len("local:"):]
    if model.startswith("nuvem:"):
        return "nuvem", "https://ollama.com", model[len("nuvem:"):]
    return ("nuvem" if "ollama.com" in host_padrao else "local"), host_padrao, model


def suporta_raciocinio(model: str) -> bool:
    base = model.split(":", 1)[-1] if model.startswith(("local:", "nuvem:")) else model
    return base.lower().startswith(PREFIXOS_RACIOCINIO)


def _think_do_ambiente() -> str | bool:
    bruto = _limpo("OLLAMA_THINK", "low").lower()
    return False if bruto in ("", "none", "false", "0") else bruto


def get_llm(
    perfil: str = PERFIL_PADRAO,
    papel: str = "principal",
    model: str | None = None,
    reasoning: str | bool | None = None,
    **sobrescritas,
) -> ChatOllama:
    """
    perfil     temperature/top_p/num_predict/seed (ver PERFIS)
    papel      principal | comparacao | extra (lido do .env)
    model      nome explícito; aceita prefixo de provedor 'local:' / 'nuvem:'
    reasoning  'low' | 'medium' | 'high' | False | 'omitir'.
               None = OLLAMA_THINK do .env, mas só para modelos de raciocínio.
    """
    if perfil not in PERFIS:
        raise ValueError(f"perfil desconhecido: {perfil!r}. Use um de {list(PERFIS)}")

    parametros = {**PERFIS[perfil], **sobrescritas}
    provedor, base_url, model = resolver_provedor(model or nome_do_modelo(papel))
    na_nuvem = provedor == "nuvem"
    api_key = _limpo("OLLAMA_API_KEY")

    if reasoning is None:
        reasoning = _think_do_ambiente() if suporta_raciocinio(model) else OMITIR
    if reasoning == OMITIR:
        reasoning = None          # None => o campo `think` não é enviado

    if na_nuvem and not api_key:
        raise RuntimeError(
            "O provedor é a nuvem (ollama.com) mas OLLAMA_API_KEY está vazia.\n"
            "Crie a chave em https://ollama.com/settings/keys"
        )

    if na_nuvem and model.endswith("-cloud"):
        # '-cloud' é para o Ollama LOCAL puxar da nuvem; direto na ollama.com o
        # nome correto é sem sufixo (senão: 404, fácil de confundir com auth).
        model = model[: -len("-cloud")]

    kwargs = {
        "model": model,
        "base_url": base_url,
        "reasoning": reasoning,
        # Não valida o modelo na construção: a fábrica é chamada em import de
        # módulo e não pode derrubar a aplicação se o servidor demorar.
        "validate_model_on_init": False,
        # Contagem de tokens local e offline, na mesma régua do eval.
        "custom_get_token_ids": tokens.ids,
        **parametros,
    }
    if na_nuvem:
        kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {api_key}"}}

    return ChatOllama(**kwargs)


def _exigir_conteudo(msg: AIMessage) -> AIMessage:
    if not str(getattr(msg, "content", "") or "").strip():
        raise RespostaVazia("modelo devolveu conteúdo vazio")
    return msg


def get_llm_robusto(perfil: str = PERFIL_PADRAO, papel: str = "principal",
                    model: str | None = None, **sobrescritas) -> Runnable:
    """
    LLM com fallback declarativo em LCEL (`with_fallbacks`).

    1ª tentativa: configuração normal.
    Fallback:     sem o campo `think` e com o dobro de orçamento de tokens.

    Cobre os dois modos de falha observados na Sprint 3: resposta vazia por
    orçamento consumido no raciocínio, e modelos que devolvem vazio quando
    recebem `think`. Sem isso, uma resposta vazia virava nota 0 no eval por um
    problema de transporte, não de qualidade.
    """
    principal = get_llm(perfil=perfil, papel=papel, model=model, **sobrescritas)
    orcamento = {**PERFIS[perfil], **sobrescritas}.get("num_predict", 1024) * 2
    reserva_kw = {k: v for k, v in sobrescritas.items() if k != "num_predict"}
    reserva = get_llm(perfil=perfil, papel=papel, model=model, reasoning=OMITIR,
                      num_predict=orcamento, **reserva_kw)
    checar = RunnableLambda(_exigir_conteudo, name="exigir_conteudo")
    return (principal | checar).with_fallbacks([reserva | checar])


def descrever(perfil: str = PERFIL_PADRAO, papel: str = "principal",
              model: str | None = None) -> dict:
    """Parâmetros efetivos — cabeçalho de cada eval e do relatório de modelos."""
    try:
        nome = model or nome_do_modelo(papel)
    except ModeloNaoConfigurado:
        nome = "(nao configurado)"
    provedor, host, nome_limpo = resolver_provedor(nome)
    think = _think_do_ambiente() if suporta_raciocinio(nome_limpo) else "nao enviado"
    return {
        "papel": papel,
        "model": nome_limpo,
        "provedor": provedor,
        "host": host,
        "perfil": perfil,
        "think": think if think is not False else "desligado",
        **PERFIS[perfil],
        "regua_tokens": tokens.nome_regua(),
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
