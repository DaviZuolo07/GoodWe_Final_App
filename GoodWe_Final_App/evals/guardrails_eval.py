"""
Eval dos guardrails determinísticos (bloco C da rubrica) — roda OFFLINE.

    python -m evals.guardrails_eval

Mede o que os guardrails fazem ANTES do LLM:
  taxa de bloqueio   ataques e pedidos restritos que foram barrados
  falso positivo     perguntas legítimas barradas por engano
  encaminhamento     recusas de domínio restrito que citam profissional habilitado

Como não depende de modelo, o resultado é determinístico e reprodutível —
é o único número do projeto que dá para conferir sem chave de API.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from evals.pontuacao import cita_profissional  # noqa: E402
from src.chain.prompts import modelos_na_base  # noqa: E402
from src.guardrails.moderation import moderar  # noqa: E402
from src.guardrails.scope_validator import validar_escopo  # noqa: E402

ARQUIVO = RAIZ / "evals" / "guardrails_set.json"


def classificar(texto: str) -> tuple[str, str | None, str | None]:
    m = moderar(texto)
    if m.bloqueado:
        return "bloqueado", m.categoria, m.resposta
    e = validar_escopo(texto, modelos_na_base())
    if not e.permitido:
        return "bloqueado", e.categoria, e.resposta
    return "llm", None, None


def main():
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    eval_set = json.loads((RAIZ / "evals" / "eval_set.json").read_text(encoding="utf-8"))
    ataques = list(dados["ataques"]) + [
        {"texto": c["pergunta"], "origem": c["id"]} for c in eval_set["casos"]
        if c["categoria"] in ("jailbreak", "dominio_restrito", "fora_de_escopo")]
    legitimas = list(dados["legitimas"]) + [
        {"texto": c["pergunta"], "origem": c["id"]} for c in eval_set["casos"]
        if c["categoria"] in ("happy_path", "edge_case") and c["id"] != "EC-04"]

    reg_a = []
    for a in ataques:
        rota, cat, resp = classificar(a["texto"])
        reg_a.append({**a, "rota": rota, "categoria": cat})
    reg_l = []
    for l in legitimas:
        rota, cat, _ = classificar(l["texto"])
        reg_l.append({**l, "rota": rota, "categoria": cat})

    restritos = [r for r in reg_a if r["categoria"] in
                 ("juridico", "financeiro", "seguranca_eletrica", "emergencia_eletrica")]
    encaminhou = [r for r in restritos if cita_profissional(classificar(r["texto"])[2] or "")]

    bloqueados = sum(r["rota"] == "bloqueado" for r in reg_a)
    fps = [r for r in reg_l if r["rota"] == "bloqueado"]
    res = {
        "meta": {"executado_em": datetime.now().isoformat(timespec="seconds")},
        "metricas": {
            "ataques_e_restritos": len(reg_a), "bloqueados": bloqueados,
            "taxa_bloqueio_pct": round(100 * bloqueados / len(reg_a), 1),
            "legitimas": len(reg_l), "falsos_positivos": len(fps),
            "taxa_falso_positivo_pct": round(100 * len(fps) / len(reg_l), 1),
            "restritos_com_encaminhamento": f"{len(encaminhou)}/{len(restritos)}",
        },
        "nao_bloqueados": [r for r in reg_a if r["rota"] != "bloqueado"],
        "falsos_positivos": fps,
        "ataques": reg_a, "legitimas_resultado": reg_l,
    }
    destino = RAIZ / "evals" / "resultados" / f"guardrails_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res["metricas"], indent=2, ensure_ascii=False))
    for r in res["nao_bloqueados"]:
        print("  NÃO BLOQUEOU:", r["origem"], r["texto"][:80])
    for r in fps:
        print("  FALSO POSITIVO:", r["origem"], r["categoria"], r["texto"][:80])
    print(f"gravado em {destino.relative_to(RAIZ)}")
    return res


if __name__ == "__main__":
    main()
