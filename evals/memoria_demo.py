"""
Demonstração da memória por sessão (item 2 do escopo: 3+ turnos).

    python -m evals.memoria_demo                   # limite padrão (1200 tokens)
    python -m evals.memoria_demo --limite 150      # força a poda da janela

Roteiro de 6 turnos em que cada turno depende dos anteriores. Duas provas:
  1. Coerência: o turno 3 calcula com dados dos turnos 1 e 2; o turno 6
     pergunta um dado do turno 1.
  2. Teto de tokens: com --limite baixo, a ConversationTokenBufferMemory
     descarta as mensagens antigas (eventos_de_poda > 0) e mesmo assim o
     turno 6 acerta, porque o fato está em <fatos_da_sessao>.

Imprime `load_memory_variables()` ao final, como pede a Aula 02.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

ROTEIRO = [
    ("Meu carro tem uma bateria de 60 kWh.", None),
    ("Agora ela está com 25%.", None),
    ("O carregador da minha vaga é de 7,4 kW. Quanto tempo leva até 80%?", ["4h59", "4h5", "5h", "4,9", "5 h"]),
    ("E se eu parar em 70%?", ["4h05", "4h0", "4h", "4,1"]),
    ("Com a tarifa de R$ 2,10 por kWh, quanto custaria essa recarga até 70%?", ["63", "64"]),
    ("Só para confirmar: qual é a capacidade da minha bateria?", ["60"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=None, help="max_token_limit da memória")
    ap.add_argument("--prompt", default="v2")
    ap.add_argument("--modelo", default=None)
    a = ap.parse_args()

    from src.chain.builder import ChatbotChargeOps
    from src.chain.memoria import MAX_TOKENS_PADRAO

    limite = a.limite or MAX_TOKENS_PADRAO
    bot = ChatbotChargeOps(versao_prompt=a.prompt, model=a.modelo, max_tokens_memoria=limite)
    sid = "demo-memoria"
    turnos = []
    print(f"max_token_limit = {limite}\n")
    for i, (pergunta, esperado) in enumerate(ROTEIRO, 1):
        r = bot.responder(pergunta, session_id=sid)
        mem = bot.memoria(sid)
        acertou = None if esperado is None else any(e in r.texto for e in esperado)
        turnos.append({"turno": i, "pergunta": pergunta, "resposta": r.texto, "esperado_contem": esperado,
                       "coerente": acertou, "calculo": r.calculo, "memoria": mem,
                       "tokens_prompt": r.tokens_prompt, "chamadas_llm": r.chamadas_llm})
        print(f"T{i} > {pergunta}\n   < {r.texto}")
        print(f"   memória: {mem['mensagens_na_janela']} msgs, {mem['tokens_na_janela']}/{limite} tokens, "
              f"podas={mem['eventos_de_poda']}, fatos={mem['fatos_da_sessao']}"
              + ("" if acertou is None else f"  | coerente={acertou}") + "\n")

    hist = bot.sessoes.obter(sid).historico
    print("load_memory_variables():")
    for m in hist.load_memory_variables()["history"]:
        print(f"   [{m.type}] {str(m.content)[:90]}")

    checaveis = [t for t in turnos if t["coerente"] is not None]
    resultado = {
        "meta": {"executado_em": datetime.now().isoformat(timespec="seconds"),
                 "max_token_limit": limite, "prompt": a.prompt},
        "coerencia": f"{sum(t['coerente'] for t in checaveis)}/{len(checaveis)}",
        "eventos_de_poda": turnos[-1]["memoria"]["eventos_de_poda"],
        "turnos": turnos,
    }
    destino = RAIZ / "evals" / "resultados" / f"memoria_limite{limite}_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ncoerência: {resultado['coerencia']} | podas: {resultado['eventos_de_poda']} | {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
