"""
Eval de STRUCTURED OUTPUT — "acurácia do structured output" do §8.

    python -m evals.structured_eval --modo manual     (coluna "antes")
    python -m evals.structured_eval --modo lcel       (coluna "depois")

manual  Como a Sprint 2 faria: o LLMProvider de ai/ (sem alteração) recebe um
        prompt pedindo JSON e o resultado passa por json.loads — sem schema,
        sem validação. É uma reconstrução do caminho manual, declarada como tal
        no relatório (a Sprint 2 não tinha saída estruturada nenhuma).
lcel    A chain da Sprint 3: prompt | ChatOllama(format="json") | PydanticOutputParser
        com field_validator, e uma autocorreção se a validação falhar.

Métricas:
  json_valido_pct        a saída é um objeto JSON parseável
  schema_valido_pct      passa no schema ConsultaRecarga (tipos, faixas, regra alvo>atual)
  acuracia_campos_pct    campos corretos / campos avaliados (null também é um valor esperado)
  casos_perfeitos_pct    todos os campos corretos
  rejeicao_correta       SO-13 (alvo < atual) precisa ser REJEITADO
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import types
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from pydantic import ValidationError  # noqa: E402

from src.schemas.consulta_recarga import ConsultaRecarga  # noqa: E402

SET = RAIZ / "evals" / "structured_set.json"
PASTA = RAIZ / "evals" / "resultados"

PROMPT_MANUAL = (
    "Extraia da mensagem do usuário um JSON com as chaves: intencao (estimativa_tempo, "
    "estimativa_custo, estado_carregador, faturamento, conceitual ou outro), capacidade_bateria_kwh, "
    "soc_atual_pct, soc_alvo_pct, potencia_carregador_kw, potencia_max_ac_veiculo_kw, tarifa_kwh_brl, "
    "energia_entregue_kwh, estado_carregador (disponivel, ocupado, reservado, offline, falha), "
    "tipo_corrente (AC ou DC). Use null para o que não foi dito. Responda só o JSON."
)


def _iguais(esperado, obtido) -> bool:
    if esperado is None:
        return obtido in (None, "", "null")
    if isinstance(esperado, (int, float)):
        try:
            return abs(float(obtido) - esperado) <= 0.01 * abs(esperado) + 1e-9
        except (TypeError, ValueError):
            return False
    return str(obtido).strip().lower() == str(esperado).strip().lower()


class ExtratorManual:
    """Caminho manual: LLMProvider do legado + json.loads, sem schema."""

    def __init__(self, papel="principal", model=None):
        from evals.adaptadores import AdaptadorLegado
        self._transporte = AdaptadorLegado(papel=papel, model=model)
        self.nome = f"manual[{self._transporte.modelo}]"

    def extrair(self, mensagem: str):
        from ai.services import llm_provider as modulo
        prov = modulo.LLMProvider()
        prov.api_url, prov.model = self._transporte.api_url, self._transporte.modelo
        original = modulo.requests
        modulo.requests = types.SimpleNamespace(post=self._transporte._post)
        try:
            bruto = prov.generate_response([{"role": "system", "content": PROMPT_MANUAL},
                                            {"role": "user", "content": mensagem}])
        finally:
            modulo.requests = original
        texto = bruto.replace("```json", "").replace("```", "").strip()
        dados = json.loads(texto[texto.find("{"): texto.rfind("}") + 1])   # pode levantar
        return dados, 1


class ExtratorLCEL:
    def __init__(self, papel="principal", model=None):
        from src.chain.builder import montar_chain_extracao
        from src.chain.llm import get_llm_robusto, nome_do_modelo
        self.modelo = model or nome_do_modelo(papel)
        self.nome = f"lcel[{self.modelo}]"
        self.chain, _ = montar_chain_extracao(
            get_llm_robusto("estruturado", model=self.modelo, format="json"))

    def extrair(self, mensagem: str):
        entrada = {"pergunta": mensagem, "historico_texto": "(vazio)", "correcao": ""}
        try:
            return self.chain.invoke(entrada).model_dump(), 1
        except Exception as e:
            entrada["correcao"] = (f"\n<erro_anterior>Seu JSON anterior foi rejeitado: {str(e)[:300]}. "
                                   "Corrija e responda só o JSON.</erro_anterior>")
            try:
                return self.chain.invoke(entrada).model_dump(), 2
            except Exception:
                raise e


def executar(modo: str, papel="principal", model=None) -> dict:
    dados = json.loads(SET.read_text(encoding="utf-8"))
    campos = dados["meta"]["campos_avaliados"]
    extrator = ExtratorManual(papel, model) if modo == "manual" else ExtratorLCEL(papel, model)
    print(f"Extrator: {extrator.nome} | casos: {len(dados['casos'])}\n")

    regs = []
    for c in dados["casos"]:
        t0 = time.perf_counter()
        saida, tentativas, erro, json_ok = None, 0, None, False
        try:
            saida, tentativas = extrator.extrair(c["mensagem"])
            json_ok = isinstance(saida, dict)
        except json.JSONDecodeError as e:
            erro = f"JSONDecodeError: {e}"
        except Exception as e:
            erro = f"{type(e).__name__}: {str(e)[:200]}"
            json_ok = "OutputParserException" not in erro and "Invalid json" not in erro
        lat = round((time.perf_counter() - t0) * 1000)

        schema_ok = False
        if saida is not None:
            try:
                ConsultaRecarga.model_validate(saida)
                schema_ok = True
            except ValidationError:
                schema_ok = False

        if not c["esperado_valido"]:
            acertos, total = (1, 1) if not schema_ok else (0, 1)   # rejeitar é o correto
        elif saida is None:
            acertos, total = 0, len(campos)   # sem saída, nenhum campo conta como acerto
        else:
            acertos = sum(_iguais(c["esperado"].get(k), saida.get(k)) for k in campos)
            total = len(campos)

        regs.append({"id": c["id"], "mensagem": c["mensagem"], "esperado": c["esperado"],
                     "obtido": saida, "erro": erro, "json_valido": json_ok, "schema_valido": schema_ok,
                     "tentativas": tentativas, "acertos": acertos, "campos": total,
                     "perfeito": acertos == total, "latencia_ms": lat})
        print(f"  {c['id']}  json={'ok' if json_ok else 'NAO'}  schema={'ok' if schema_ok else 'NAO'}  "
              f"campos {acertos}/{total}  {lat} ms" + (f"  [{erro[:60]}]" if erro else ""))

    validos_esperados = [r for r, c in zip(regs, dados["casos"]) if c["esperado_valido"]]
    resumo = {
        "meta": {"extrator": extrator.nome, "modo": modo, "set_versao": dados["meta"]["versao"],
                 "executado_em": datetime.now().isoformat(timespec="seconds")},
        "metricas": {
            "json_valido_pct": round(100 * sum(r["json_valido"] for r in validos_esperados) / len(validos_esperados), 1),
            "schema_valido_pct": round(100 * sum(r["schema_valido"] for r in validos_esperados) / len(validos_esperados), 1),
            "acuracia_campos_pct": round(100 * sum(r["acertos"] for r in regs) / sum(r["campos"] for r in regs), 1),
            "casos_perfeitos_pct": round(100 * sum(r["perfeito"] for r in regs) / len(regs), 1),
            "precisou_autocorrecao": sum(1 for r in regs if r["tentativas"] == 2),
            "latencia_media_ms": round(statistics.mean(r["latencia_ms"] for r in regs)),
        },
        "casos": regs,
    }
    return resumo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["manual", "lcel"], default="lcel")
    ap.add_argument("--papel", default="principal")
    ap.add_argument("--modelo", default=None)
    a = ap.parse_args()
    r = executar(a.modo, a.papel, a.modelo)
    PASTA.mkdir(parents=True, exist_ok=True)
    nome = r["meta"]["extrator"].replace(":", "-")
    destino = PASTA / f"structured_{nome}_{datetime.now():%Y%m%d_%H%M%S}.json"
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n", json.dumps(r["metricas"], indent=2, ensure_ascii=False))
    print(f"  gravado em: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
