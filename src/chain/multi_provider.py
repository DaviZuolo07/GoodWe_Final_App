"""
BÔNUS (+1) — chamada multi-provider: mais de um MODELO e mais de um PROMPT.

    python -m src.chain.multi_provider "Quanto tempo para carregar 60 kWh de 20 a 80% em 7,4 kW?"
    python -m src.chain.multi_provider "..." --modelos gpt-oss:120b,gemma4:31b,local:qwen3:8b --prompts v1,v2

Monta uma matriz modelo x prompt e dispara TODAS as combinações em paralelo
com um único RunnableParallel (LCEL). "Multi-provider" é literal: o prefixo
`local:` manda a chamada para o Ollama da máquina e o nome sem prefixo vai
para a Ollama Cloud — dois endpoints, duas credenciais, uma chamada.

Cada ramo mede sua própria latência e tokens; uma falha num ramo (modelo
inexistente, servidor local desligado) vira registro de erro, não derruba os
outros. Grava evals/resultados/multi_provider_<carimbo>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel

from src.chain import prompts, tokens
from src.chain.builder import renderizar_perfil
from src.chain.llm import get_llm_robusto, modelos_configurados, resolver_provedor

RAIZ = Path(__file__).resolve().parents[2]


def _ramo(modelo: str, versao: str):
    template = prompts.montar_template(versao)
    chain = template | get_llm_robusto("redator", model=modelo) | StrOutputParser()

    def executar(entrada: dict) -> dict:
        provedor = resolver_provedor(modelo)[0]
        t0 = time.perf_counter()
        try:
            texto = chain.invoke(entrada)
            erro = None
        except Exception as e:
            texto, erro = "", f"{type(e).__name__}: {str(e)[:160]}"
        msgs = template.format_messages(**entrada)
        return {"modelo": modelo, "provedor": provedor, "prompt": versao, "resposta": texto, "erro": erro,
                "latencia_ms": round((time.perf_counter() - t0) * 1000),
                "tokens_prompt": tokens.contar_mensagens(msgs), "tokens_resposta": tokens.contar(texto)}

    return RunnableLambda(executar, name=f"{modelo}|{versao}")


def comparar(pergunta: str, modelos: list[str], versoes: list[str]) -> list[dict]:
    ramos = {f"{m} | {v}": _ramo(m, v) for m in modelos for v in versoes}
    paralelo = RunnableParallel(**ramos)
    entrada = {"pergunta": pergunta, "perfil_usuario": renderizar_perfil(None, "morador"),
               "fatos_sessao": "nenhum dado informado nesta sessão",
               "calculo_verificado": "nenhum cálculo necessário nesta mensagem"}
    return list(paralelo.invoke(entrada).values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pergunta")
    ap.add_argument("--modelos", default=None, help="lista separada por vírgula (padrão: todos do .env)")
    ap.add_argument("--prompts", default="v1,v2")
    a = ap.parse_args()
    modelos = a.modelos.split(",") if a.modelos else list(modelos_configurados().values())
    if len(modelos) < 2:
        sys.exit("Configure ao menos 2 modelos (OLLAMA_MODEL e OLLAMA_MODEL_B) ou use --modelos.")
    res = comparar(a.pergunta, modelos, a.prompts.split(","))
    for r in res:
        print(f"\n=== {r['modelo']} ({r['provedor']}) | prompt {r['prompt']} | {r['latencia_ms']} ms | "
              f"{r['tokens_prompt']}+{r['tokens_resposta']} tokens")
        print(r["erro"] or r["resposta"])
    destino = RAIZ / "evals" / "resultados" / f"multi_provider_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"pergunta": a.pergunta, "resultados": res}, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(f"\ngravado em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
