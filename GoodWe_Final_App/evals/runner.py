"""
Runner do eval — executa o eval set contra um adaptador e grava o resultado.

    python -m evals.runner --adaptador falso --sem-juiz          (teste seco, sem rede)
    python -m evals.runner --adaptador legado                    (coluna "antes")
    python -m evals.runner --adaptador lcel_cru                  (efeito só do framework)
    python -m evals.runner --adaptador lcel --prompt v1
    python -m evals.runner --adaptador lcel --prompt v2          (coluna "depois")
    python -m evals.runner --adaptador lcel --prompt v2 --sem-guardrails   (ablação)
    python -m evals.runner --adaptador lcel --papel comparacao   (2º modelo)

Cada execução grava `evals/resultados/<config>_<carimbo>.json` com TUDO por caso.
Qualquer número da tabela do relatório é rastreável até o caso que o gerou.

MÉTRICAS DO §8
  qualidade           nota do juiz (0-2) ponderada pelo peso + conformidade determinística
  tokens por turno    régua tiktoken o200k_harmony (prompt + resposta de TODAS as chamadas)
                      + tokens reais do servidor (usage_metadata, inclui raciocínio)
  latência            perf_counter em volta do responder()
  structured output   taxa de JSON válido na 1ª tentativa nos turnos que acionaram a
                      extração (a acurácia campo a campo vem de evals/structured_eval.py)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from evals import pontuacao  # noqa: E402
from evals.adaptadores import ADAPTADORES  # noqa: E402
from src.chain import tokens  # noqa: E402

EVAL_SET = RAIZ / "evals" / "eval_set.json"
PASTA_RESULTADOS = RAIZ / "evals" / "resultados"


def carregar_casos() -> tuple[dict, list]:
    dados = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    casos = [c for c in dados["casos"] if not c.get("invalidado") and "PREENCHER" not in c["pergunta"]]
    return dados["meta"], casos


def _media(valores):
    valores = [v for v in valores if v is not None]
    return round(statistics.mean(valores), 1) if valores else None


def executar(adaptador_nome: str, papel: str = "principal", modelo: str | None = None,
             versao_prompt: str = "v2", guardrails: bool = True, usar_juiz: bool = True,
             limite: int | None = None, verboso: bool = True) -> dict:
    if adaptador_nome not in ADAPTADORES:
        raise SystemExit(f"adaptador desconhecido: {adaptador_nome}. Use um de {list(ADAPTADORES)}")
    adaptador = ADAPTADORES[adaptador_nome](papel=papel, model=modelo,
                                            versao_prompt=versao_prompt, guardrails=guardrails)
    meta, casos = carregar_casos()
    if limite:
        casos = casos[:limite]

    julgar = None
    if usar_juiz:
        from evals.juiz import MODELO_JUIZ, julgar as _julgar
        julgar = _julgar
        if verboso:
            print(f"Juiz: {MODELO_JUIZ} (fora dos modelos avaliados, evita auto-preferência)")
    if verboso:
        print(f"Adaptador: {adaptador.nome} | casos: {len(casos)} | régua: {tokens.nome_regua()}\n")

    registros = []
    for i, caso in enumerate(casos, 1):
        pergunta, persona, perfil = caso["pergunta"], caso.get("persona", "morador"), caso.get("perfil")
        if verboso:
            print(f"[{i:>2}/{len(casos)}] {caso['id']:<7} {caso['categoria']:<17} ", end="", flush=True)

        inicio = time.perf_counter()
        erro = None
        try:
            resposta = adaptador.responder(pergunta, persona, perfil)
        except Exception as e:
            resposta, erro = "", f"{type(e).__name__}: {str(e)[:300]}"
        latencia_ms = round((time.perf_counter() - inicio) * 1000)
        ex = dict(getattr(adaptador, "ultima_execucao", {}) or {})

        checado = pontuacao.avaliar(resposta, caso.get("checagens"))
        veredito = {"nota": None, "recusou": None, "justificativa": "juiz desativado"}
        if julgar and not erro:
            veredito = julgar(caso, resposta)

        divergencia = (veredito.get("recusou") is not None
                       and checado["detalhes"].get("recusa_detectada") is not None
                       and bool(veredito["recusou"]) != bool(checado["detalhes"]["recusa_detectada"]))

        registros.append({
            "id": caso["id"], "categoria": caso["categoria"], "origem": caso.get("origem"),
            "persona": persona, "peso": caso.get("peso", 1),
            "pergunta": pergunta, "resposta": resposta, "erro": erro,
            "conforme": checado["conforme"], "falhas": checado["falhas"],
            "detalhes_checagem": checado["detalhes"],
            "nota_juiz": veredito["nota"], "recusou_juiz": veredito["recusou"],
            "justificativa_juiz": veredito["justificativa"],
            "divergencia_juiz_checador": divergencia,
            "rota": ex.get("rota", "llm"), "categoria_guardrail": ex.get("categoria_guardrail"),
            "chamadas_llm": ex.get("chamadas_llm", 0),
            "tokens_prompt": ex.get("tokens_prompt", 0),
            "tokens_resposta": ex.get("tokens_resposta", tokens.contar(resposta)),
            "tokens_turno": ex.get("tokens_prompt", 0) + ex.get("tokens_resposta", tokens.contar(resposta)),
            "tokens_servidor_entrada": ex.get("tokens_servidor_entrada", 0),
            "tokens_servidor_saida": ex.get("tokens_servidor_saida", 0),
            "latencia_ms": latencia_ms,
            "structured_output_valido": ex.get("estruturado_valido"),
            "structured_output_tentativas": ex.get("estruturado_tentativas", 0),
            "saida_corrigida": ex.get("saida_corrigida"),
        })
        if verboso:
            marca = "ERRO " + erro[:60] if erro else (
                f"nota {veredito['nota'] if veredito['nota'] is not None else '-'} "
                + ("conforme" if checado["conforme"] else f"FALHOU {checado['falhas']}"))
            print(f"{latencia_ms:>6} ms  {ex.get('rota', 'llm'):<18} {marca}")

    return montar_resumo(adaptador, meta, registros, papel, modelo, versao_prompt, guardrails)


def montar_resumo(adaptador, meta, registros, papel, modelo, versao, guardrails) -> dict:
    validos = [r for r in registros if not r["erro"]]
    com_nota = [r for r in validos if r["nota_juiz"] is not None]
    peso_total = sum(r["peso"] for r in com_nota)
    nota = sum(r["nota_juiz"] * r["peso"] for r in com_nota) / peso_total if peso_total else None
    com_llm = [r for r in validos if r["chamadas_llm"] > 0]
    estr = [r for r in validos if r["structured_output_valido"] is not None]

    por_categoria = {}
    for r in registros:
        c = por_categoria.setdefault(r["categoria"], {"n": 0, "conformes": 0, "notas": [], "lat": []})
        c["n"] += 1
        c["conformes"] += int(r["conforme"])
        if r["nota_juiz"] is not None:
            c["notas"].append(r["nota_juiz"])
        if not r["erro"]:
            c["lat"].append(r["latencia_ms"])
    for c in por_categoria.values():
        c["nota_media"] = round(statistics.mean(c.pop("notas")), 2) if c["notas"] else None
        c["latencia_media_ms"] = round(statistics.mean(c["lat"])) if c["lat"] else None
        c.pop("lat")
        c["conformidade_pct"] = round(100 * c["conformes"] / c["n"], 1)

    latencias = [r["latencia_ms"] for r in validos]
    try:
        from src.chain.llm import descrever
        parametros = descrever(perfil="redator", papel=papel, model=modelo)
    except Exception:
        parametros = {}

    return {
        "meta": {
            "adaptador": adaptador.nome, "tipo": type(adaptador).__name__,
            "versao_prompt": versao if "LCEL" in type(adaptador).__name__ and "Cru" not in type(adaptador).__name__ else None,
            "guardrails": guardrails, "parametros": parametros,
            "executado_em": datetime.now().isoformat(timespec="seconds"),
            "eval_set_versao": meta.get("versao"), "pontuacao_versao": pontuacao.PONTUACAO_VERSAO,
            "regua_tokens": tokens.nome_regua(),
            "total_casos": len(registros), "casos_com_erro": len(registros) - len(validos),
        },
        "metricas": {
            "nota_ponderada": round(nota, 3) if nota is not None else None,
            "nota_maxima": 2.0,
            "casos_com_nota": len(com_nota),
            "conformidade_pct": round(100 * sum(r["conforme"] for r in registros) / len(registros), 1) if registros else 0,
            "tokens_por_turno_media": _media([r["tokens_turno"] for r in validos]),
            "tokens_por_turno_com_llm_media": _media([r["tokens_turno"] for r in com_llm]),
            "tokens_servidor_por_turno_media": _media([r["tokens_servidor_entrada"] + r["tokens_servidor_saida"] for r in validos]),
            "chamadas_llm_por_turno": _media([r["chamadas_llm"] for r in validos]),
            "latencia_media_ms": round(statistics.mean(latencias)) if latencias else None,
            "latencia_mediana_ms": round(statistics.median(latencias)) if latencias else None,
            "latencia_p90_ms": round(sorted(latencias)[int(0.9 * (len(latencias) - 1))]) if latencias else None,
            "turnos_resolvidos_por_guardrail": sum(1 for r in validos if r["rota"] != "llm"),
            "structured_turnos_acionados": len(estr),
            "structured_valido_1a_tentativa_pct": round(100 * sum(1 for r in estr if r["structured_output_valido"]) / len(estr), 1) if estr else None,
            "divergencias_juiz_checador": sum(1 for r in registros if r["divergencia_juiz_checador"]),
        },
        "por_categoria": por_categoria,
        "casos": registros,
    }


def gravar(resultado: dict) -> Path:
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome = resultado["meta"]["adaptador"].replace("/", "_").replace(":", "-").replace(",", "_")
    destino = PASTA_RESULTADOS / f"{nome}_{carimbo}.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino


def main():
    ap = argparse.ArgumentParser(description="Runner do eval da Sprint 03")
    ap.add_argument("--adaptador", default="falso", choices=list(ADAPTADORES))
    ap.add_argument("--papel", default="principal", choices=["principal", "comparacao", "extra"])
    ap.add_argument("--modelo", default=None, help="nome explícito (aceita local:/nuvem:)")
    ap.add_argument("--prompt", default="v2", help="versão do system prompt (adaptador lcel)")
    ap.add_argument("--sem-guardrails", action="store_true", help="ablação: desliga guardrails")
    ap.add_argument("--sem-juiz", action="store_true", help="pula o juiz LLM")
    ap.add_argument("--limite", type=int, default=None)
    a = ap.parse_args()

    r = executar(a.adaptador, a.papel, a.modelo, a.prompt, not a.sem_guardrails, not a.sem_juiz, a.limite)
    destino = gravar(r)
    m = r["metricas"]
    print("\n" + "=" * 66)
    for chave in ("nota_ponderada", "conformidade_pct", "tokens_por_turno_media",
                  "tokens_servidor_por_turno_media", "latencia_media_ms",
                  "structured_valido_1a_tentativa_pct", "turnos_resolvidos_por_guardrail"):
        print(f"  {chave:<36} {m[chave]}")
    print("=" * 66)
    for cat, d in sorted(r["por_categoria"].items()):
        print(f"  {cat:<18} nota {str(d['nota_media']):<5} conformidade {d['conformidade_pct']}%")
    erros = r["meta"]["casos_com_erro"]
    if erros:
        print(f"\n  !!! {erros} de {r['meta']['total_casos']} casos falharam (rede/credencial/modelo).")
        print("      Resultado com falhas NÃO entra nos relatórios. Rode 'python -m src.teste_auth'.")
    print(f"\n  gravado em: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
