"""
A primeira chain LCEL do projeto.
"""

import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.chain.llm import descrever, get_llm

# ---------------------------------------------------------------------------
# 1. PROMPT
# ---------------------------------------------------------------------------
# ChatPromptTemplate não é uma f-string com nome bonito. Ele guarda os PAPÉIS
# (system / human / assistant) separados, o que é o que permite, no passo 4,
# enfiar o histórico da conversa no meio sem remontar string na mão.
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Você é o ChargeOps AI, assistente da GoodWe especializado em recarga de "
     "veículos elétricos em condomínios residenciais. Responda em português do "
     "Brasil, em no máximo três frases, sem markdown."),
    ("human", "{pergunta}"),
])

# ---------------------------------------------------------------------------
# 2. A CHAIN
# ---------------------------------------------------------------------------
# prompt | llm | parser  -->  dict entra, string sai.
# Sem o parser, sairia um AIMessage e todo consumidor precisaria saber disso.
chain = prompt | get_llm(perfil="redator") | StrOutputParser()


if __name__ == "__main__":
    print("=" * 66)
    print("PRIMEIRA CHAIN LCEL - GoodWe ChargeOps Sprint 03")
    print("=" * 66)
    for chave, valor in descrever(perfil="redator").items():
        print(f"  {chave:<12} {valor}")
    print("=" * 66)

    perguntas = [
        "Quanto tempo leva para carregar uma bateria de 60 kWh num carregador de 7,4 kW?",
        "Qual a diferença entre carregamento AC e DC?",
        "Qual a previsão do tempo para amanhã?",   # fora de escopo, de propósito
    ]

    for pergunta in perguntas:
        print(f"\n> {pergunta}")
        inicio = time.perf_counter()
        try:
            resposta = chain.invoke({"pergunta": pergunta})
            print(resposta)
            print(f"  [{time.perf_counter() - inicio:.2f}s]")
        except Exception as e:
            print(f"  [ERRO] {type(e).__name__}: {e}")
            print("  Rode 'python -m src.diagnostico' para descobrir o motivo.")
            break

    print("\n" + "=" * 66)
    print("Repare na terceira resposta: sem guardrail formal, o escopo depende")
    print("só da boa vontade do prompt. É isso que o passo 3 vai consertar.")
    print("=" * 66)
