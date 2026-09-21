"""
Checklist automático da entrega da Sprint 03.

    python -m evals.validar_entrega

Percorre a rubrica (blocos A, B, C, D + bônus) e as condições de entrega (§10),
olhando os artefatos que existem no repositório. Não julga qualidade de texto —
isso é a parte manual, descrita em docs/VALIDACAO.md.

Saída: OK / FALTA / AVISO por item, e código de saída 1 se algo obrigatório falta.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

RES = RAIZ / "evals" / "resultados"
itens: list[tuple[str, str, str, str]] = []   # (bloco, item, status, detalhe)


def add(bloco, item, ok, detalhe="", obrigatorio=True):
    itens.append((bloco, item, "OK" if ok else ("FALTA" if obrigatorio else "AVISO"), detalhe))


def _jsons(prefixo=""):
    for p in sorted(RES.glob(f"{prefixo}*.json")):
        try:
            yield p, json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue


def execucoes_validas() -> dict:
    """Execuções do eval sem falhas de rede/credencial, a mais recente por adaptador."""
    saida = {}
    for _, d in _jsons():
        m = d.get("meta", {})
        if "metricas" not in d or m.get("adaptador") in (None, "falso") or not m.get("pontuacao_versao"):
            continue
        if m.get("casos_com_erro", 0) > 0.2 * max(m.get("total_casos", 1), 1):
            continue
        k = m["adaptador"]
        if k not in saida or m["executado_em"] > saida[k]["meta"]["executado_em"]:
            saida[k] = d
    return saida


def main():
    # ---------------- Bloco A: refactory LangChain -------------------------
    ev = execucoes_validas()
    tem = lambda pref: [k for k in ev if k.startswith(pref)]  # noqa: E731
    add("A", "Chain LCEL existe e responde (execução do eval registrada)",
        bool(tem("lcel_v")), ", ".join(tem("lcel_v")) or "nenhuma execução válida do adaptador lcel")

    mem = [d for _, d in _jsons("memoria_")]
    ultima_mem = max(mem, key=lambda d: d["meta"]["executado_em"]) if mem else None
    if ultima_mem:
        acertos, total = ultima_mem["coerencia"].split("/")
        add("A", "Memória demonstrada em 3+ turnos com coerência",
            int(acertos) == int(total) and len(ultima_mem["turnos"]) >= 3,
            f"turnos={len(ultima_mem['turnos'])}, coerência={ultima_mem['coerencia']}, "
            f"podas={ultima_mem['eventos_de_poda']}")
        poda = [d for d in mem if d["eventos_de_poda"] > 0]
        add("A", "Poda da janela de tokens demonstrada", bool(poda),
            "rode: python -m evals.memoria_demo --limite 150", obrigatorio=False)
    else:
        add("A", "Memória demonstrada em 3+ turnos", False, "rode: python -m evals.memoria_demo")

    estr = {d["meta"]["extrator"]: d for _, d in _jsons("structured_")}
    lcel_estr = [d for k, d in estr.items() if k.startswith("lcel")]
    add("A", "Structured output validado pelo schema Pydantic",
        bool(lcel_estr) and all(d["metricas"]["schema_valido_pct"] >= 90 for d in lcel_estr),
        "; ".join(f"{k}: schema {d['metricas']['schema_valido_pct']}%, "
                  f"acurácia {d['metricas']['acuracia_campos_pct']}%" for k, d in estr.items()) or
        "rode: python -m evals.structured_eval --modo lcel")

    # ---------------- Bloco B: prompt versionado + modelos ------------------
    versoes = sorted((RAIZ / "prompts").glob("system_prompt_v*.md"))
    add("B", "Prompts versionados em prompts/", len(versoes) >= 2,
        ", ".join(p.name for p in versoes))
    readme_p = RAIZ / "prompts" / "README.md"
    add("B", "Tabela de versões com ganho medido",
        readme_p.exists() and "pendente" not in readme_p.read_text(encoding="utf-8"),
        "células pendentes na tabela de versões" if readme_p.exists() else "prompts/README.md não existe")
    modelos_medidos = {re.search(r"\[(.*?)[,\]]", k).group(1) for k in tem("lcel_v2")}
    add("B", "2+ modelos comparados no mesmo eval", len(modelos_medidos) >= 2,
        ", ".join(sorted(modelos_medidos)) or "defina OLLAMA_MODEL_B e rode executar_tudo")
    rel_mod = RAIZ / "docs" / "relatorio_modelos.md"
    add("B", "relatorio_modelos.md com temperature/top_p/max_tokens",
        rel_mod.exists() and "temperature" in rel_mod.read_text(encoding="utf-8"), rel_mod.name)

    # ---------------- Bloco C: guardrails -----------------------------------
    guards = [d for _, d in _jsons("guardrails_")]
    if guards:
        g = max(guards, key=lambda d: d["meta"]["executado_em"])["metricas"]
        add("C", "Ataques e pedidos restritos bloqueados", g["taxa_bloqueio_pct"] >= 100,
            f"{g['bloqueados']}/{g['ataques_e_restritos']}")
        add("C", "Sem bloquear pergunta legítima", g["taxa_falso_positivo_pct"] <= 5,
            f"falso positivo {g['taxa_falso_positivo_pct']}% em {g['legitimas']} perguntas")
        add("C", "Recusa de domínio restrito encaminha a profissional",
            g["restritos_com_encaminhamento"].split("/")[0] == g["restritos_com_encaminhamento"].split("/")[1],
            g["restritos_com_encaminhamento"])
    else:
        add("C", "Eval de guardrails executado", False, "rode: python -m evals.guardrails_eval")

    # ---------------- Bloco D: eval, evolução e relatório -------------------
    eval_set = json.loads((RAIZ / "evals" / "eval_set.json").read_text(encoding="utf-8"))
    add("D", "Eval set sem placeholders",
        not any("PREENCHER" in c["pergunta"] for c in eval_set["casos"]),
        f"{len(eval_set['casos'])} casos, versão {eval_set['meta']['versao']}")
    add("D", "Coluna 'antes' (legado) reexecutada", bool(tem("legado")),
        ", ".join(tem("legado")) or "rode: python -m evals.runner --adaptador legado")
    com_juiz = [k for k, d in ev.items() if d["metricas"].get("nota_ponderada") is not None]
    add("D", "Notas do juiz presentes", len(com_juiz) >= 2,
        ", ".join(com_juiz) or "rode o eval SEM --sem-juiz")
    tab = RAIZ / "docs" / "tabela_antes_depois.md"
    add("D", "Tabela antes/depois sem pendências",
        tab.exists() and "pendente" not in tab.read_text(encoding="utf-8"),
        "há células 'pendente'" if tab.exists() else "não gerada")
    pdf = RAIZ / "docs" / "relatorio_evolucao.pdf"
    paginas = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes())) if pdf.exists() else 0
    add("D", "Relatório de evolução em PDF com até 5 páginas",
        pdf.exists() and 0 < paginas <= 5, f"{paginas} página(s)" if pdf.exists() else "não gerado")
    eq = json.loads((RAIZ / "docs" / "equipe.json").read_text(encoding="utf-8"))
    falta_eq = [i["nome"] for i in eq["integrantes"] if "PREENCHER" in i["tarefa_principal"]]
    add("D", "Equipe e divisão de trabalho preenchidas", not falta_eq,
        "faltam: " + ", ".join(falta_eq) if falta_eq else f"{len(eq['integrantes'])} integrantes")
    add("D", "Consolidado sprint3_results.json", (RAIZ / "evals" / "sprint3_results.json").exists())

    # ---------------- Bônus ---------------------------------------------------
    multi = list(_jsons("multi_provider_"))
    ok_multi = False
    if multi:
        r = multi[-1][1]["resultados"]
        ok_multi = len({x["modelo"] for x in r}) >= 2 and len({x["prompt"] for x in r}) >= 2 \
            and all(not x["erro"] for x in r)
    add("Bônus", "Multi-provider: 2+ modelos e 2+ prompts sem erro", ok_multi,
        "rode: python -m src.chain.multi_provider \"...\"", obrigatorio=False)

    # ---------------- §10 Condições de entrega --------------------------------
    testes = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                            cwd=RAIZ, capture_output=True, text=True)
    add("§10", "Testes offline passando", testes.returncode == 0,
        testes.stdout.strip().splitlines()[-1] if testes.stdout else "")

    git = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True)
    versionados = git.stdout.splitlines() if git.returncode == 0 else []
    add("§10", ".env fora do controle de versão", ".env" not in versionados,
        "git não inicializado aqui" if not versionados else "", obrigatorio=bool(versionados))
    vazamento = []
    for arquivo in versionados:
        caminho = RAIZ / arquivo
        if caminho.suffix in (".py", ".md", ".json", ".txt", ".example") and caminho.exists():
            try:
                texto = caminho.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if re.search(r"OLLAMA_API_KEY\s*[=:]\s*['\"]?[A-Za-z0-9]{20,}", texto):
                vazamento.append(arquivo)
    add("§10", "Nenhuma chave de API versionada", not vazamento, ", ".join(vazamento))
    if versionados:
        autores = subprocess.run(["git", "log", "--format=%an"], cwd=RAIZ,
                                 capture_output=True, text=True).stdout.split("\n")
        add("§10", "Commits de mais de um integrante", len({a for a in autores if a.strip()}) >= 2,
            ", ".join(sorted({a for a in autores if a.strip()})), obrigatorio=False)

    # ---------------- Relatório ------------------------------------------------
    largura = max(len(i[1]) for i in itens) + 2
    bloco_atual = None
    for bloco, item, status, detalhe in itens:
        if bloco != bloco_atual:
            print(f"\n=== {bloco} " + "=" * (largura + 14 - len(bloco)))
            bloco_atual = bloco
        marca = {"OK": "[ok]   ", "FALTA": "[FALTA]", "AVISO": "[aviso]"}[status]
        print(f" {marca} {item:<{largura}} {detalhe}")

    faltas = [i for i in itens if i[2] == "FALTA"]
    print("\n" + "=" * (largura + 20))
    print(f" {len(itens) - len(faltas)}/{len(itens)} itens ok" +
          (f" — {len(faltas)} obrigatório(s) faltando" if faltas else " — entrega completa"))
    print(" Validação manual (leitura das respostas): docs/VALIDACAO.md")
    return 1 if faltas else 0


if __name__ == "__main__":
    sys.exit(main())
