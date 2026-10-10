"""
Fallback manual do RAGAS (§8 do enunciado): LLM-as-judge com rubrica 0–1.

Roda SEMPRE junto do RAGAS no `ragas_eval.py`, não só quando ele quebra. Dois
motivos: (1) se o RAGAS falhar na véspera, o número das duas iterações já
existe na mesma régua; (2) as duas medidas lado a lado mostram se o ganho é do
sistema ou artefato de uma métrica.

Rubrica (padrão da Aula 07, slide "Fallback — RAGAS manual") e a justificativa
da equivalência com o RAGAS estão em `evals/rubrica_manual.md`.

O juiz é um modelo FIXO (`MODELO_JUIZ`, perfil `classificador`: temperature 0,
seed 42) e é o mesmo nas duas iterações — mudar o juiz muda a régua.
"""

from __future__ import annotations

import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.chain.llm import get_llm_robusto

INVALIDO = -1.0   # sentinela da Aula 07: o juiz respondeu algo que não é número

PROMPT_FIDELIDADE = """<tarefa>
Você é um avaliador de qualidade de sistemas RAG.
Avalie se a RESPOSTA está fundamentada no CONTEXTO.
Citações no formato (fonte: documento, página X) não contam como afirmação.
</tarefa>

<contexto>
{contexto}
</contexto>

<resposta>
{resposta}
</resposta>

Responda APENAS com um número de 0 a 1:
- 1.0: toda a resposta está no contexto
- 0.5: resposta parcialmente no contexto
- 0.0: resposta inventa informações não presentes no contexto

Resposta (só o número):"""

PROMPT_RELEVANCIA = """<tarefa>
Você é um avaliador de qualidade de sistemas RAG.
Avalie se a RESPOSTA aborda diretamente o que a PERGUNTA pediu.
Não julgue se a resposta é verdadeira, só se ela responde à pergunta feita.
</tarefa>

<pergunta>
{pergunta}
</pergunta>

<resposta>
{resposta}
</resposta>

Responda APENAS com um número de 0 a 1:
- 1.0: responde diretamente e por completo ao que foi perguntado
- 0.5: responde em parte, ou responde com desvio de foco
- 0.0: não responde à pergunta (recusa, evasiva ou outro assunto)

Resposta (só o número):"""

_NUMERO = re.compile(r"(?<![\d.])(0(?:[.,]\d+)?|1(?:[.,]0+)?)(?![\d.])")


def ler_nota(texto: str) -> float:
    """Primeiro número entre 0 e 1 da saída; o modelo às vezes devolve texto junto."""
    try:
        return float(texto.strip().replace(",", "."))
    except ValueError:
        m = _NUMERO.search(texto or "")
        return float(m.group(1).replace(",", ".")) if m else INVALIDO


class JuizRAG:
    def __init__(self, modelo: str):
        self.modelo = modelo
        llm = get_llm_robusto("classificador", model=modelo)
        self._fidelidade = ChatPromptTemplate.from_template(PROMPT_FIDELIDADE) | llm | StrOutputParser()
        self._relevancia = ChatPromptTemplate.from_template(PROMPT_RELEVANCIA) | llm | StrOutputParser()

    def fidelidade(self, resposta: str, contextos: list[str]) -> float:
        if not contextos:
            return INVALIDO
        return ler_nota(self._fidelidade.invoke({"contexto": "\n\n---\n\n".join(contextos),
                                                 "resposta": resposta}))

    def relevancia(self, pergunta: str, resposta: str) -> float:
        return ler_nota(self._relevancia.invoke({"pergunta": pergunta, "resposta": resposta}))
