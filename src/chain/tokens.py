"""
Régua de tokens da Sprint 03 (Aula 04 — context engineering).

DECISÃO: a régua padrão é `o200k_harmony`, não `cl100k_base`.

O gpt-oss (modelo principal) foi publicado pela OpenAI com o tokenizador
`o200k_harmony` — o mesmo vocabulário do `o200k_base` acrescido dos tokens
especiais do formato de chat "harmony". O tiktoken >= 0.10 traz esse encoding.
Resultado: para o texto enviado ao gpt-oss, a contagem desta régua é a do
próprio modelo, e não uma aproximação. A versão anterior do runner usava
`cl100k_base` (tokenizador do GPT-4), que conta ~10–20% a mais em português.

Para os outros modelos (gemma, qwen, glm) a contagem continua sendo uma
APROXIMAÇÃO, e o relatório diz isso. O que importa numa comparação é usar a
MESMA régua em todas as colunas — e é o que este módulo garante: todo o projeto
(runner, memória, relatório) conta tokens por aqui.

A contagem REAL de cada chamada (inclusive tokens de raciocínio) vem do próprio
servidor em `usage_metadata` e é registrada separadamente pelo eval.
"""

from __future__ import annotations

import functools
import os
import re
from typing import Iterable

# Overhead do formato harmony por mensagem: <|start|>{role}<|message|> ... <|end|>
# = 3 tokens especiais + 1 do papel. É a mesma ordem de grandeza do overhead
# documentado pela OpenAI para o formato ChatML (3–4 tokens/mensagem).
OVERHEAD_POR_MENSAGEM = 4

ORDEM_DE_PREFERENCIA = ("o200k_harmony", "o200k_base", "cl100k_base")


@functools.lru_cache(maxsize=1)
def _codificador():
    """Carrega o melhor encoding disponível; None se o tiktoken não conseguir."""
    preferido = (os.getenv("TIKTOKEN_ENCODING") or "").strip()
    candidatos = ((preferido,) if preferido else ()) + ORDEM_DE_PREFERENCIA
    try:
        import tiktoken
    except ImportError:
        return None, "sem_tiktoken"

    for nome in candidatos:
        try:
            return tiktoken.get_encoding(nome), nome
        except Exception:  # encoding inexistente ou arquivo BPE sem internet
            continue
    return None, "sem_tiktoken"


def nome_regua() -> str:
    """Nome do encoding em uso — vai no cabeçalho de todo resultado de eval."""
    return _codificador()[1]


def ids(texto: str) -> list[int]:
    """
    Tokeniza. Passado ao ChatOllama como `custom_get_token_ids`, faz a
    ConversationTokenBufferMemory contar tokens com esta régua em vez de tentar
    baixar o tokenizador GPT-2 do `transformers` (que nem está instalado).
    """
    cod, _ = _codificador()
    if cod is None:
        # Fallback declarado: ~1 token a cada 4 caracteres (heurística usual).
        return list(range(max(1, len(texto or "") // 4))) if texto else []
    return cod.encode(texto or "", disallowed_special=())


def contar(texto: str) -> int:
    return len(ids(texto))


def contar_mensagens(mensagens: Iterable) -> int:
    """
    Tokens de uma lista de mensagens LangChain ou dicts {role, content}.
    Soma conteúdo + overhead fixo do formato de chat por mensagem.
    """
    total = 0
    for m in mensagens:
        conteudo = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if not isinstance(conteudo, str):
            conteudo = str(conteudo)
        total += contar(conteudo) + OVERHEAD_POR_MENSAGEM
    return total


_RE_ESPACO = re.compile(r"\s+")


def densidade(texto: str) -> float:
    """Caracteres por token — útil para comparar prolixidade entre versões."""
    n = contar(texto)
    return round(len(_RE_ESPACO.sub(" ", texto or "")) / n, 2) if n else 0.0
