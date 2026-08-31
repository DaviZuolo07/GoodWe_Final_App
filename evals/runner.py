"""
Runner do eval — executa o eval set contra um adaptador e grava o resultado.

    python -m evals.runner --adaptador falso                 (teste seco, sem rede)
    python -m evals.runner --adaptador legado                (coluna "antes")
    python -m evals.runner --adaptador lcel_cru              (piso do LCEL)
    python -m evals.runner --adaptador lcel_cru --modelo gpt-oss:20b --sem-juiz

Cada execução grava `evals/resultados/<adaptador>_<carimbo>.json` com TUDO:
pergunta, resposta crua, checagens, nota do juiz, tokens, latência. Nada de
média solta — a tabela do relatório é derivada desse arquivo, e qualquer número
dela pode ser rastreado até o caso que o gerou. É isso que se responde quando a
banca pergunta "de onde saiu esse 1,7?".

AS QUATRO MÉTRICAS QUE O §8 EXIGE
---------------------------------
  qualidade das respostas  -> nota do juiz (0-2), ponderada pelo peso do caso
  tokens por turno         -> tiktoken sobre prompt + resposta
  latência média           -> perf_counter em volta do responder()
  acurácia structured out. -> N/A até o passo 6; o campo já existe, zerado
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from evals import pontuacao  # noqa: E402
from evals.adaptadores import ADAPTADORES  # noqa: E402

EVAL_SET = RAIZ / "evals" / "eval_set.json"
PASTA_RESULTADOS = RAIZ / "evals" / "resultados"


def contar_tokens(texto: str) -> int:
    """
    Contagem via tiktoken/cl100k_base.

    É uma APROXIMAÇÃO: gpt-oss, gemma e glm usam tokenizadores diferentes deste.
    O número absoluto não é exato, e o relatório precisa dizer isso.

    O que importa aqui é ser a MESMA régua para todas as colunas. Para responder
    "o prompt v2 gastou menos tokens que o v1?" ou "o LCEL gasta mais que o
    legado?", uma régua consistente e levemente errada serve; réguas diferentes
    por coluna não serviriam de nada.
    """
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(texto or ""))
    except Exception:
        return len((texto or "").split())


def carregar_casos(incluir_pendentes: bool) -> tuple:
    dados = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    casos = [c for c in dados["casos"] if not c.get("invalidado")]

    pendentes = [c for c in casos if "PREENCHER" in c.get("pergunta", "")]
    if pendentes and not incluir_pendentes:
        print(f"[aviso] {len(pendentes)} caso(s) ainda com PREENCHER: "
              f"{', '.join(c['id'] for c in pendentes)}")
        print("        Eles ficam de fora desta execução. Preencha os S12-* com")
        print("        as perguntas originais do docs/test_cases.md antes do")
        print("        baseline oficial — o §8 exige o MESMO eval set das Sprints 1/2.\n")
        casos = [c for c in casos if c not in pendentes]

    return dados["meta"], casos


def executar(nome_adaptador: str, modelo: str | None, usar_juiz: bool,
             limite: int | None, incluir_pendentes: bool) -> dict:

    if nome_adaptador not in ADAPTADORES:
        raise SystemExit(f"adaptador desconhecido: {nome_adaptador}. "
                         f"Use um de {list(ADAPTADORES)}")

    classe = ADAPTADORES[nome_adaptador]
    adaptador = classe(model=modelo) if nome_adaptador == "lcel_cru" else classe()

    meta, casos = carregar_casos(incluir_pendentes)
    if limite:
        casos = casos[:limite]

    julgar = None
    if usar_juiz:
        from evals.juiz import MODELO_JUIZ, julgar as _julgar
        julgar = _julgar
        print(f"Juiz: {MODELO_JUIZ} (fora da lista de modelos avaliados, "
              f"para evitar viés de auto-preferência)")

    print(f"Adaptador: {adaptador.nome}")
    print(f"Casos: {len(casos)}\n")

    registros = []

    for i, caso in enumerate(casos, 1):
        pergunta = caso["pergunta"]
        persona = caso.get("persona", "morador")

        print(f"[{i:>2}/{len(casos)}] {caso['id']:<7} {caso['categoria']:<17} ", end="", flush=True)

        try:
            prompt_txt = adaptador.prompt_renderizado(pergunta, persona)
        except Exception:
            prompt_txt = pergunta

        inicio = time.perf_counter()
        erro = None
        try:
            resposta = adaptador.responder(pergunta, persona)
        except Exception as e:
            resposta, erro = "", f"{type(e).__name__}: {e}"
        latencia_ms = round((time.perf_counter() - inicio) * 1000)

        checado = pontuacao.avaliar(resposta, caso.get("checagens"))

        veredito = {"nota": None, "recusou": None, "justificativa": "juiz desativado"}
        if julgar and not erro:
            veredito = julgar(caso, resposta)

        # Divergência entre o checador determinístico e o juiz LLM. Não é bug:
        # é o sinal de que o caso merece olho humano. A lista de divergências
        # vale um parágrafo em "problemas encontrados e soluções".
        divergencia = (
            veredito.get("recusou") is not None
            and checado["detalhes"].get("recusa_detectada") is not None
            and bool(veredito["recusou"]) != bool(checado["detalhes"]["recusa_detectada"])
        )

        registros.append({
            "id": caso["id"],
            "categoria": caso["categoria"],
            "origem": caso.get("origem"),
            "persona": persona,
            "peso": caso.get("peso", 1),
            "pergunta": pergunta,
            "resposta": resposta,
            "erro": erro,
            "conforme": checado["conforme"],
            "falhas": checado["falhas"],
            "detalhes_checagem": checado["detalhes"],
            "nota_juiz": veredito["nota"],
            "recusou_juiz": veredito["recusou"],
            "justificativa_juiz": veredito["justificativa"],
            "divergencia_juiz_checador": divergencia,
            "tokens_prompt": contar_tokens(prompt_txt),
            "tokens_resposta": contar_tokens(resposta),
            "tokens_turno": contar_tokens(prompt_txt) + contar_tokens(resposta),
            "latencia_ms": latencia_ms,
            "structured_output_valido": None,   # preenchido a partir do passo 6
        })

        if erro:
            marca = "ERRO"
        else:
            marca = f"nota {veredito['nota'] if veredito['nota'] is not None else '-'}"
            marca += " conforme" if checado["conforme"] else f" FALHOU({len(checado['falhas'])})"
        print(f"{latencia_ms:>6} ms  {marca}")

    return montar_resumo(adaptador, meta, registros)


def montar_resumo(adaptador, meta, registros: list) -> dict:
    validos = [r for r in registros if not r["erro"]]
    com_nota = [r for r in validos if r["nota_juiz"] is not None]

    peso_total = sum(r["peso"] for r in com_nota)
    nota_ponderada = (
        sum(r["nota_juiz"] * r["peso"] for r in com_nota) / peso_total
        if peso_total else None
    )

    por_categoria = {}
    for r in registros:
        cat = por_categoria.setdefault(r["categoria"], {"n": 0, "conformes": 0, "notas": []})
        cat["n"] += 1
        cat["conformes"] += 1 if r["conforme"] else 0
        if r["nota_juiz"] is not None:
            cat["notas"].append(r["nota_juiz"])

    for cat in por_categoria.values():
        cat["nota_media"] = round(statistics.mean(cat["notas"]), 2) if cat["notas"] else None
        cat["conformidade_pct"] = round(100 * cat["conformes"] / cat["n"], 1)
        del cat["notas"]

    latencias = [r["latencia_ms"] for r in validos]

    return {
        "meta": {
            "adaptador": adaptador.nome,
            "executado_em": datetime.now().isoformat(timespec="seconds"),
            "eval_set_versao": meta.get("versao"),
            "total_casos": len(registros),
            "casos_com_erro": len(registros) - len(validos),
        },
        "metricas": {
            "nota_ponderada": round(nota_ponderada, 3) if nota_ponderada is not None else None,
            "nota_maxima": 2.0,
            "conformidade_pct": round(100 * sum(1 for r in registros if r["conforme"]) / len(registros), 1) if registros else 0,
            "tokens_por_turno_media": round(statistics.mean(r["tokens_turno"] for r in validos)) if validos else None,
            "latencia_media_ms": round(statistics.mean(latencias)) if latencias else None,
            "latencia_mediana_ms": round(statistics.median(latencias)) if latencias else None,
            "acuracia_structured_output": None,
            "divergencias_juiz_checador": sum(1 for r in registros if r["divergencia_juiz_checador"]),
        },
        "por_categoria": por_categoria,
        "casos": registros,
    }


def main():
    ap = argparse.ArgumentParser(description="Runner do eval da Sprint 03")
    ap.add_argument("--adaptador", default="falso", choices=list(ADAPTADORES))
    ap.add_argument("--modelo", default=None, help="sobrescreve o modelo (só lcel_cru)")
    ap.add_argument("--sem-juiz", action="store_true", help="pula o juiz LLM (mais rápido, sem cota)")
    ap.add_argument("--limite", type=int, default=None, help="roda só os N primeiros casos")
    ap.add_argument("--incluir-pendentes", action="store_true",
                    help="inclui os casos ainda com PREENCHER")
    args = ap.parse_args()

    resultado = executar(args.adaptador, args.modelo, not args.sem_juiz,
                         args.limite, args.incluir_pendentes)

    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_limpo = resultado["meta"]["adaptador"].replace("/", "_").replace(":", "-")
    destino = PASTA_RESULTADOS / f"{nome_limpo}_{carimbo}.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")

    m = resultado["metricas"]
    print("\n" + "=" * 66)
    print(f"  nota ponderada .......... {m['nota_ponderada']} / 2.0")
    print(f"  conformidade ............ {m['conformidade_pct']}%")
    print(f"  tokens por turno ........ {m['tokens_por_turno_media']}")
    print(f"  latência média .......... {m['latencia_media_ms']} ms")
    print(f"  divergências juiz/check . {m['divergencias_juiz_checador']}")
    print("=" * 66)
    print("\n  por categoria:")
    for cat, d in sorted(resultado["por_categoria"].items()):
        print(f"    {cat:<18} nota {str(d['nota_media']):<5} "
              f"conformidade {d['conformidade_pct']}%")
    print(f"\n  gravado em: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
