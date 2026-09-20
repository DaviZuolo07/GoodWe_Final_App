"""
Executa a bateria completa da Sprint 03 e gera todos os relatórios.

    python -m evals.executar_tudo                 # completo (com juiz)
    python -m evals.executar_tudo --sem-juiz      # sem notas do juiz (mais rápido)
    python -m evals.executar_tudo --rapido        # só o essencial p/ a tabela antes/depois

Ordem:
  1. guardrails (offline)
  2. eval 28 casos: legado -> lcel_cru -> lcel v1 -> lcel v2 (principal)
  3. ablação: lcel v2 sem guardrails                   (pulado em --rapido)
  4. lcel v2 com os modelos de comparação (B, C)       (bloco B, relatório de modelos)
  5. structured output: manual x lcel (principal e comparação)
  6. demonstração de memória (limite padrão e limite 150)
  7. gerar_relatorios -> sprint3_results.json, tabelas, relatorio_modelos.md, PDF

Uma etapa que falha é registrada e a bateria continua.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def etapa(nome, fn, falhas):
    print("\n" + "#" * 70 + f"\n# {nome}\n" + "#" * 70)
    try:
        fn()
    except Exception as e:
        falhas.append(f"{nome}: {type(e).__name__}: {e}")
        traceback.print_exc()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-juiz", action="store_true")
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args()

    from evals import runner, structured_eval
    from src.chain.llm import modelos_configurados

    juiz = not a.sem_juiz
    modelos = modelos_configurados()
    falhas: list[str] = []

    def rodar(adaptador, papel="principal", versao="v2", guardrails=True):
        r = runner.executar(adaptador, papel=papel, versao_prompt=versao, guardrails=guardrails, usar_juiz=juiz)
        print("  ->", runner.gravar(r).relative_to(RAIZ))

    def estruturado(modo, papel="principal"):
        import json
        from datetime import datetime
        r = structured_eval.executar(modo, papel)
        destino = RAIZ / "evals" / "resultados" / (
            f"structured_{r['meta']['extrator'].replace(':', '-')}_{datetime.now():%Y%m%d_%H%M%S}.json")
        destino.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")

    etapa("guardrails (offline)", lambda: subprocess.run(
        [sys.executable, "-m", "evals.guardrails_eval"], cwd=RAIZ, check=True), falhas)
    etapa("legado (Sprint 2)", lambda: rodar("legado"), falhas)
    etapa("lcel_cru", lambda: rodar("lcel_cru"), falhas)
    etapa("lcel v1", lambda: rodar("lcel", versao="v1"), falhas)
    etapa("lcel v2", lambda: rodar("lcel", versao="v2"), falhas)
    if not a.rapido:
        etapa("ablação: lcel v2 sem guardrails", lambda: rodar("lcel", versao="v2", guardrails=False), falhas)
    for papel in ("comparacao", "extra"):
        if papel in modelos and not (a.rapido and papel == "extra"):
            etapa(f"lcel v2 [{modelos[papel]}]", lambda p=papel: rodar("lcel", papel=p), falhas)
    etapa("structured manual", lambda: estruturado("manual"), falhas)
    etapa("structured lcel", lambda: estruturado("lcel"), falhas)
    if "comparacao" in modelos:
        etapa("structured lcel [comparacao]", lambda: estruturado("lcel", "comparacao"), falhas)
    etapa("memória (limite padrão)", lambda: subprocess.run(
        [sys.executable, "-m", "evals.memoria_demo"], cwd=RAIZ, check=True), falhas)
    if not a.rapido:
        etapa("memória (limite 150, força poda)", lambda: subprocess.run(
            [sys.executable, "-m", "evals.memoria_demo", "--limite", "150"], cwd=RAIZ, check=True), falhas)
    etapa("relatórios", lambda: subprocess.run(
        [sys.executable, "-m", "evals.gerar_relatorios"], cwd=RAIZ, check=True), falhas)

    print("\n" + "=" * 70)
    print("CONCLUÍDO" + (f" com {len(falhas)} falha(s):" if falhas else " sem falhas."))
    for f in falhas:
        print("  -", f)


if __name__ == "__main__":
    main()
