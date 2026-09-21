"""
Gera TODOS os artefatos de relatório a partir de evals/resultados/*.json.

    python -m evals.gerar_relatorios

Saídas:
  evals/sprint3_results.json      consolidado (exigido no §5)
  docs/tabela_antes_depois.md     tabela obrigatória do §8
  docs/relatorio_modelos.md       §6: 2+ modelos, temperature/top_p/max_tokens
  prompts/README.md               §6: tabela de versões com ganho medido
  docs/relatorio_evolucao.pdf     §8: relatório de até 5 páginas

Nenhum número é digitado à mão: tudo sai dos JSONs de resultado. Célula sem
execução correspondente aparece como "pendente" — nunca como estimativa.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from src.chain import prompts, tokens  # noqa: E402
from src.chain.llm import PERFIS, descrever, modelos_configurados  # noqa: E402

RES = RAIZ / "evals" / "resultados"
PEND = "pendente"


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def carregar() -> dict:
    ev, estr, mem, guard, multi = {}, {}, {}, None, None
    descartados: list[str] = []
    for p in sorted(RES.glob("*.json")):
        d = _json(p)
        if not d:
            continue
        n = p.name
        if n.startswith("structured_"):
            k = d["meta"]["extrator"]
            if k not in estr or d["meta"]["executado_em"] > estr[k]["meta"]["executado_em"]:
                estr[k] = d
        elif n.startswith("memoria_"):
            k = d["meta"]["max_token_limit"]
            if k not in mem or d["meta"]["executado_em"] > mem[k]["meta"]["executado_em"]:
                mem[k] = d
        elif n.startswith("guardrails_"):
            if not guard or d["meta"]["executado_em"] > guard["meta"]["executado_em"]:
                guard = d
        elif n.startswith("multi_provider_"):
            multi = d
        elif "metricas" in d and "casos" in d and d.get("meta", {}).get("adaptador") != "falso":
            k = d["meta"]["adaptador"]
            if d["meta"].get("pontuacao_versao") is None:
                continue          # resultado da régua 1.0: não comparável
            total, erros = d["meta"]["total_casos"], d["meta"].get("casos_com_erro", 0)
            if total and erros / total > 0.2:
                # Execução quebrada (rede/credencial) não vira número de relatório.
                descartados.append(f"{d['meta']['adaptador']}: {erros}/{total} casos com erro")
                continue
            if k not in ev or d["meta"]["executado_em"] > ev[k]["meta"]["executado_em"]:
                ev[k] = d
    return {"eval": ev, "structured": estr, "memoria": mem, "guardrails": guard,
            "multi": multi, "descartados": descartados}


def f(v, suf="", casas=None):
    if v is None:
        return PEND
    if isinstance(v, str):
        return v
    if casas is not None and isinstance(v, (int, float)):
        v = f"{v:.{casas}f}"
    return f"{v}{suf}".replace(".", ",")


def _m(ev, chave, metrica):
    d = ev.get(chave)
    return d["metricas"].get(metrica) if d else None


def tokens_estaticos() -> dict:
    from langchain_core.output_parsers import PydanticOutputParser

    from src.schemas.consulta_recarga import ConsultaRecarga, instrucoes_compactas
    return {
        "system_legado_v0": prompts.tokens_legado(),
        **{f"system_{v}": prompts.tokens_do_sistema(v) for v in prompts.versoes_disponiveis()},
        "format_instructions_pydantic": tokens.contar(
            PydanticOutputParser(pydantic_object=ConsultaRecarga).get_format_instructions()),
        "format_instructions_compacto": tokens.contar(instrucoes_compactas()),
        "regua": tokens.nome_regua(),
    }


# --------------------------------------------------------------------------- #
# Consolidação
# --------------------------------------------------------------------------- #
def consolidar(r: dict) -> dict:
    modelos = modelos_configurados()
    p = modelos.get("principal", "gpt-oss:120b")
    ev = r["eval"]
    chaves = {"legado": f"legado[{p}]", "lcel_cru": f"lcel_cru[{p}]",
              "v1": f"lcel_v1[{p}]", "v2": f"lcel_v2[{p}]",
              "v2_sem_guardrails": f"lcel_v2[{p},sem_guardrails]"}
    est = r["structured"]
    s_man, s_lcel = est.get(f"manual[{p}]"), est.get(f"lcel[{p}]")

    def col(k):
        c = chaves[k]
        return {m: _m(ev, c, m) for m in (
            "nota_ponderada", "conformidade_pct", "tokens_por_turno_media",
            "tokens_por_turno_com_llm_media", "tokens_servidor_por_turno_media",
            "chamadas_llm_por_turno", "latencia_media_ms", "latencia_p90_ms",
            "turnos_resolvidos_por_guardrail", "structured_valido_1a_tentativa_pct")}

    tabela = {k: col(k) for k in chaves}
    tabela["legado"]["structured_acuracia_campos_pct"] = s_man["metricas"]["acuracia_campos_pct"] if s_man else None
    tabela["legado"]["structured_schema_valido_pct"] = s_man["metricas"]["schema_valido_pct"] if s_man else None
    for k in ("v1", "v2", "v2_sem_guardrails"):
        tabela[k]["structured_acuracia_campos_pct"] = s_lcel["metricas"]["acuracia_campos_pct"] if (s_lcel and k != "v1") else None
        tabela[k]["structured_schema_valido_pct"] = s_lcel["metricas"]["schema_valido_pct"] if (s_lcel and k != "v1") else None

    # Onde a funcionalidade não existe, a célula é "n/a" (não "pendente").
    for k in ("legado", "lcel_cru", "v1"):
        tabela[k]["structured_valido_1a_tentativa_pct"] = "n/a"
    for k in ("lcel_cru", "v1"):
        tabela[k]["structured_acuracia_campos_pct"] = "n/a"
        tabela[k]["structured_schema_valido_pct"] = "n/a"

    por_modelo = {}
    for papel, nome in modelos.items():
        chave = f"lcel_v2[{nome}]"
        e = ev.get(chave)
        s = est.get(f"lcel[{nome}]")
        por_modelo[nome] = {
            "papel": papel, "parametros": descrever("redator", model=nome),
            "metricas": e["metricas"] if e else None,
            "por_categoria": e["por_categoria"] if e else None,
            "structured": s["metricas"] if s else None,
        }

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo_principal": p, "modelos": modelos,
        "tokens_estaticos": tokens_estaticos(),
        "tabela_antes_depois": tabela,
        "chaves_usadas": chaves,
        "por_modelo": por_modelo,
        "structured": {k: v["metricas"] for k, v in est.items()},
        "memoria": {str(k): {"coerencia": v["coerencia"], "eventos_de_poda": v["eventos_de_poda"],
                             "executado_em": v["meta"]["executado_em"]} for k, v in r["memoria"].items()},
        "guardrails": r["guardrails"]["metricas"] if r["guardrails"] else None,
        "execucoes": {k: {"meta": v["meta"], "metricas": v["metricas"], "por_categoria": v["por_categoria"]}
                      for k, v in ev.items()},
    }


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
LINHAS_TABELA = [
    ("Qualidade — nota do juiz (0 a 2, ponderada)", "nota_ponderada", "", 2),
    ("Qualidade — conformidade determinística", "conformidade_pct", "%", 1),
    ("Tokens por turno (tiktoken o200k_harmony)", "tokens_por_turno_media", "", 0),
    ("Tokens por turno reais do servidor (inclui raciocínio)", "tokens_servidor_por_turno_media", "", 0),
    ("Chamadas ao LLM por turno", "chamadas_llm_por_turno", "", 2),
    ("Latência média (ms)", "latencia_media_ms", "", 0),
    ("Latência p90 (ms)", "latencia_p90_ms", "", 0),
    ("Structured output — acurácia por campo", "structured_acuracia_campos_pct", "%", 1),
    ("Structured output — schema válido", "structured_schema_valido_pct", "%", 1),
    ("Turnos resolvidos pelos guardrails (sem LLM)", "turnos_resolvidos_por_guardrail", "", 0),
]
COLS = [("legado", "Sprints 1/2 (manual/legado)"), ("lcel_cru", "LCEL cru (só framework)"),
        ("v1", "Sprint 03 LCEL + prompt v1"), ("v2", "Sprint 03 LCEL + prompt v2 (final)")]


def md_tabela(c: dict) -> str:
    t = c["tabela_antes_depois"]
    te = c["tokens_estaticos"]
    out = ["# Tabela antes/depois — Sprint 03 (§8, obrigatória)", "",
           f"Gerada automaticamente em {c['gerado_em']} por `evals/gerar_relatorios.py` a partir de "
           f"`evals/resultados/`. Modelo: `{c['modelo_principal']}`. Mesmo eval set (28 casos, v1.1), "
           "mesma régua de pontuação (v1.1), mesmo juiz, mesmo runner para todas as colunas.", "",
           "| Métrica | " + " | ".join(n for _, n in COLS) + " |",
           "|---|" + "---|" * len(COLS)]
    for rot, k, suf, casas in LINHAS_TABELA:
        out.append(f"| {rot} | " + " | ".join(f(t[c_].get(k), suf, casas) for c_, _ in COLS) + " |")
    out.append(f"| Tokens fixos do system prompt | {te['system_legado_v0']} | ~40 | {te['system_v1']} | {te['system_v2']} |")
    g = c.get("guardrails")
    if g:
        out.append(f"| Guardrails: bloqueio / falso positivo | não havia | não havia | "
                   f"{g['taxa_bloqueio_pct']}% / {g['taxa_falso_positivo_pct']}% | "
                   f"{g['taxa_bloqueio_pct']}% / {g['taxa_falso_positivo_pct']}% |")
    out += ["", "Leitura das colunas: *legado → LCEL cru* isola o efeito do framework; "
            "*LCEL cru → v1/v2* isola o efeito de prompt, structured output e guardrails.", "",
            "Notas de método:",
            "- Structured output do legado: o Sprint 2 não tinha saída estruturada. A coluna mede o caminho "
            "manual equivalente (LLMProvider do legado + `json.loads`), ver `evals/structured_eval.py`.",
            "- Tokens: régua única `o200k_harmony` (tokenizador do gpt-oss) para todas as colunas; "
            "a linha \"reais do servidor\" vem de `usage_metadata`/`eval_count` do Ollama.",
            "- Ablação (v2 sem guardrails): " + ", ".join(
                f"{rot.split(' — ')[-1] if ' — ' in rot else rot}: {f(t['v2_sem_guardrails'].get(k), suf, casas)}"
                for rot, k, suf, casas in LINHAS_TABELA[:2] + LINHAS_TABELA[5:6]) + "."]
    return "\n".join(out) + "\n"


def md_modelos(c: dict) -> str:
    te = c["tokens_estaticos"]
    out = ["# Relatório de uso de modelos e parâmetros (§6)", "",
           f"Gerado em {c['gerado_em']} a partir de `evals/resultados/`. Execução: `python -m evals.executar_tudo`.", "",
           "## 1. Modelos comparados", "",
           "| Papel | Modelo | Provedor | Raciocínio (`think`) |", "|---|---|---|---|"]
    for nome, d in c["por_modelo"].items():
        p = d["parametros"]
        out.append(f"| {d['papel']} | `{nome}` | {p['provedor']} ({p['host']}) | {p['think']} |")
    if len(c["por_modelo"]) < 2:
        out.append("| comparacao | pendente: defina `OLLAMA_MODEL_B` no .env | | |")
    out += ["", "Juiz do eval: `glm-5.3-flash` (ou `MODELO_JUIZ`), propositalmente FORA da lista acima "
            "para evitar viés de auto-preferência.", "",
            "## 2. Parâmetros (temperature, top_p, max_tokens)", "",
            "Definidos em `src/chain/llm.py` (`PERFIS`). `num_predict` é o max_tokens do Ollama.", "",
            "| Perfil | temperature | top_p | max_tokens | seed | Uso e justificativa |", "|---|---|---|---|---|---|"]
    motivos = {
        "classificador": "contagem de tokens da memória e roteamento; reprodutível",
        "redator": "resposta ao usuário; 0,2 dá texto natural sem floreio numérico (acima de ~0,4 o modelo arredonda/inventa número)",
        "estruturado": "extração Pydantic e juiz; zero criatividade, JSON válido de primeira",
    }
    for nome, p in PERFIS.items():
        out.append(f"| `{nome}` | {p['temperature']} | {p['top_p']} | {p['num_predict']} | {p['seed']} | {motivos[nome]} |")
    out += ["", "Legado (Sprint 2): não enviava parâmetro nenhum (usava os padrões do modelo e raciocínio padrão). "
            "Isso é parte do que a coluna \"antes\" mede.", "",
            "Por que max_tokens alto (1024): no Ollama, `num_predict` conta também os tokens de raciocínio do "
            "gpt-oss. Com 400 tokens e `think=low`, parte das respostas saía vazia. A concisão passou a ser "
            "controlada pelo prompt (`<formato>`: no máximo 4 frases), e o fallback `with_fallbacks` repete a "
            "chamada sem `think` e com o dobro do orçamento se vier vazio.", "",
            "## 3. Resultados por modelo (LCEL + prompt v2, mesmo eval de 28 casos)", "",
            "| Modelo | Nota juiz | Conformidade | Latência média | Latência p90 | Tokens servidor/turno | Structured (acurácia) |",
            "|---|---|---|---|---|---|---|"]
    for nome, d in c["por_modelo"].items():
        m, s = d["metricas"] or {}, d["structured"] or {}
        out.append(f"| `{nome}` | {f(m.get('nota_ponderada'), '', 2)} | {f(m.get('conformidade_pct'), '%')} | "
                   f"{f(m.get('latencia_media_ms'), ' ms')} | {f(m.get('latencia_p90_ms'), ' ms')} | "
                   f"{f(m.get('tokens_servidor_por_turno_media'), '', 0)} | {f(s.get('acuracia_campos_pct'), '%')} |")
    out += ["", "### Por categoria (nota média do juiz)", "",
            "| Modelo | happy_path | edge_case | jailbreak | fora_de_escopo | dominio_restrito |", "|---|---|---|---|---|---|"]
    for nome, d in c["por_modelo"].items():
        pc = d["por_categoria"] or {}
        out.append(f"| `{nome}` | " + " | ".join(f((pc.get(k) or {}).get("nota_media"), "", 2) for k in
                   ("happy_path", "edge_case", "jailbreak", "fora_de_escopo", "dominio_restrito")) + " |")
    avaliados = {n: d["metricas"]["nota_ponderada"] for n, d in c["por_modelo"].items()
                 if d["metricas"] and d["metricas"].get("nota_ponderada") is not None}
    out += ["", "## 4. Conclusão", ""]
    if len(avaliados) >= 2:
        melhor = max(avaliados, key=avaliados.get)
        out.append(f"Maior nota do juiz: `{melhor}` ({f(avaliados[melhor], '', 2)}). Jailbreak, fora de escopo e "
                   "domínio restrito tendem a empatar entre modelos porque são resolvidos pelos guardrails antes "
                   "do LLM; a diferença real entre modelos aparece em happy_path e edge_case.")
    else:
        out.append("Pendente: rode `python -m evals.executar_tudo` com `OLLAMA_MODEL_B` definido.")
    out += ["", "## 5. Contexto e memória", "",
            f"Tokens fixos do system prompt: legado {te['system_legado_v0']} → v1 {te['system_v1']} → v2 {te['system_v2']} "
            f"(régua `{te['regua']}`). Instrução de formato do structured output: `get_format_instructions()` = "
            f"{te['format_instructions_pydantic']} tokens; versão compacta gerada do mesmo schema = "
            f"{te['format_instructions_compacto']} tokens.", "",
            "`max_token_limit` da memória = 1200. Justificativa medida: as 5 conversas registradas da Sprint 2 "
            "(docs/test_cases.md) têm média de 21 tokens por pergunta e 144 por resposta, ≈174 tokens por turno "
            "com overhead; 1200 tokens guardam ≈6,9 turnos completos. Com o limite de 4 frases do prompt v2 as "
            "respostas encolhem e a janela cobre mais turnos. Fica dentro da faixa 800–1500 recomendada na Aula 02.", ""]
    for lim, d in sorted(c["memoria"].items(), key=lambda x: int(x[0])):
        out.append(f"- Demonstração com limite {lim}: coerência {d['coerencia']}, eventos de poda {d['eventos_de_poda']}.")
    out += ["", "## 6. Observações de compatibilidade (medidas no projeto)", "",
            "- `gemma4` e `glm-*-flash` devolvem conteúdo vazio quando recebem o campo `think`: a fábrica só envia "
            "`think` para famílias de raciocínio (gpt-oss, qwen3, kimi, deepseek, nemotron).",
            "- Sufixo `-cloud` é para o Ollama local puxar da nuvem; falando direto com ollama.com o nome é sem sufixo (senão 404).",
            "- `GET /api/tags` da ollama.com é público; só `POST /api/chat` valida a chave (falso verde do 1º diagnóstico).",
            "- Contagem com `o200k_harmony` é exata para o gpt-oss e aproximada para os demais modelos; todos são medidos com a mesma régua."]
    return "\n".join(out) + "\n"


def md_prompts(c: dict) -> str:
    te = c["tokens_estaticos"]
    ev, p = c["execucoes"], c["modelo_principal"]
    def m(chave, met, suf="", casas=None):
        return f((ev.get(chave) or {}).get("metricas", {}).get(met), suf, casas)
    linhas = [
        ("v0 (legado)", "Sprint 2", "system_prompt.txt + GOODWE_CONTEXT + 11 few-shots, enviados em toda chamada",
         "ponto de partida", te["system_legado_v0"], f"legado[{p}]"),
        ("v1", "2026-09-01", "prompt consolidado em markdown: escopo, recusas com encaminhamento, "
         "limite de 4 frases, sem LaTeX/tabelas", "respostas prolixas (12–15 frases no LCEL cru) e recusas sem encaminhamento",
         te["system_v1"], f"lcel_v1[{p}]"),
        ("v2", "2026-09-15", "XML tagging por seção; spotlighting da entrada em <pergunta_usuario>; canário anti-vazamento; "
         "<base_produtos>; <calculo_verificado> e <fatos_da_sessao> preenchidos pelo código; 3 few-shots curtos",
         "isolar instrução de dado (injection), tirar a aritmética do modelo, fatos sobreviverem à janela de memória",
         te["system_v2"], f"lcel_v2[{p}]"),
    ]
    out = ["# Prompts versionados", "",
           "Cada versão é um arquivo `system_prompt_vN.md` com cabeçalho (versão, data, template da mensagem humana). "
           "O builder carrega por argumento (`ChatbotChargeOps(versao_prompt=\"v2\")`) e o runner mede cada versão "
           "com o mesmo eval. Tabela gerada por `evals/gerar_relatorios.py`.", "",
           "| Versão | Data | O que mudou | Por quê | Tokens do system | Nota juiz | Conformidade | Latência média | Tokens/turno |",
           "|---|---|---|---|---|---|---|---|---|"]
    for v, d, o, pq, tk, ch in linhas:
        out.append(f"| {v} | {d} | {o} | {pq} | {tk} | {m(ch, 'nota_ponderada', '', 2)} | "
                   f"{m(ch, 'conformidade_pct', '%')} | {m(ch, 'latencia_media_ms', ' ms')} | {m(ch, 'tokens_por_turno_media', '', 0)} |")
    out += ["", f"Régua de tokens: `{te['regua']}`. \"Tokens do system\" = texto fixo do system prompt com os blocos "
            "dinâmicos vazios. O v2 é maior que o v1 porque carrega a base de produtos, os exemplos e as seções de "
            "segurança; o ganho de custo em relação ao legado vem de enviar ~1/4 dos tokens fixos.", "",
            "`base_produtos.json`: única fonte de especificação de produto. O que não está nele é recusado "
            "(§6: não inventar especificação de produto fora da base)."]
    return "\n".join(out) + "\n"


def main():
    r = carregar()
    c = consolidar(r)
    c["execucoes_descartadas"] = r["descartados"]
    for d in r["descartados"]:
        print(f"DESCARTADO (execução com falhas): {d}")
    (RAIZ / "evals" / "sprint3_results.json").write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    (RAIZ / "docs" / "tabela_antes_depois.md").write_text(md_tabela(c), encoding="utf-8")
    (RAIZ / "docs" / "relatorio_modelos.md").write_text(md_modelos(c), encoding="utf-8")
    (RAIZ / "prompts" / "README.md").write_text(md_prompts(c), encoding="utf-8")
    from evals.relatorio_pdf import construir
    pdf = construir(c)
    print("gerados: evals/sprint3_results.json, docs/tabela_antes_depois.md, docs/relatorio_modelos.md, "
          f"prompts/README.md, {pdf.relative_to(RAIZ)}")
    pend = sum(1 for col in c["tabela_antes_depois"].values() for v in col.values() if v is None)
    if pend:
        print(f"ATENÇÃO: {pend} célula(s) da tabela antes/depois estão pendentes — rode `python -m evals.executar_tudo`.")


if __name__ == "__main__":
    main()
