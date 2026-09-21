"""Schema Pydantic v2 + calculadora (contas conferidas à mão no comentário)."""
import pytest
from pydantic import ValidationError

from src.dominio.recarga import calcular, horas_para_texto
from src.schemas.consulta_recarga import ConsultaRecarga, mesclar_fatos, numero_br


@pytest.mark.parametrize("entrada,esperado", [
    ("7,4", 7.4), ("7,4 kW", 7.4), ("80%", 80.0), ("R$ 2,10", 2.1),
    ("1.234,5", 1234.5), ("7.4", 7.4), ("1.234.567", 1234567.0), (None, None), ("null", None), (60, 60.0),
])
def test_numero_br(entrada, esperado):
    assert numero_br(entrada) == esperado


def test_field_validators_normalizam():
    c = ConsultaRecarga(capacidade_bateria_kwh="44,9 kWh", soc_atual_pct="20%", estado_carregador="Livre",
                        tipo_corrente="corrente alternada", confianca="85%")
    assert (c.capacidade_bateria_kwh, c.soc_atual_pct, c.estado_carregador, c.tipo_corrente, c.confianca) == \
        (44.9, 20.0, "disponivel", "AC", 0.85)


def test_validacao_rejeita_alvo_menor_que_atual():
    with pytest.raises(ValidationError):
        ConsultaRecarga(soc_atual_pct=90, soc_alvo_pct=80)


def test_validacao_rejeita_faixa_e_estado_desconhecido():
    with pytest.raises(ValidationError):
        ConsultaRecarga(capacidade_bateria_kwh=900)
    with pytest.raises(ValidationError):
        ConsultaRecarga(estado_carregador="teleportando")


def test_calculo_ac_hp01():
    # 60 kWh x 80% = 48 kWh; 48 / (7,4 x 0,894) = 7,2556 h = 7h15
    r = calcular(ConsultaRecarga(capacidade_bateria_kwh=60, soc_atual_pct=20, soc_alvo_pct=100,
                                 potencia_carregador_kw=7.4))
    assert r.energia_bateria_kwh == 48.0
    assert r.tempo_central_h == pytest.approx(7.256, abs=1e-3)
    assert horas_para_texto(r.tempo_central_h) == "7h15"
    assert r.tempo_min_h < r.tempo_central_h < r.tempo_max_h
    assert r.custo_brl is None          # tarifa não informada -> não inventa custo


def test_calculo_caso_sprint2_com_custo():
    # 44,9 x 80% = 35,92 kWh; /0,894 = 40,18 kWh da rede; x 2,10 = R$ 84,38; tempo 5h26
    r = calcular(ConsultaRecarga(capacidade_bateria_kwh=44.9, soc_atual_pct=20, soc_alvo_pct=100,
                                 potencia_carregador_kw=7.4, tarifa_kwh_brl=2.10))
    assert r.custo_brl == pytest.approx(84.38, abs=0.01)
    assert horas_para_texto(r.tempo_central_h) == "5h26"


def test_limite_do_carregador_de_bordo():
    r = calcular(ConsultaRecarga(capacidade_bateria_kwh=60, soc_atual_pct=30, soc_alvo_pct=80,
                                 potencia_carregador_kw=22, potencia_max_ac_veiculo_kw=6.6))
    assert r.potencia_efetiva_kw == 6.6


def test_dados_insuficientes():
    r = calcular(ConsultaRecarga(capacidade_bateria_kwh=60))
    assert r.status == "dados_insuficientes" and len(r.faltantes) == 3


def test_mesclar_fatos_nao_apaga_e_resolve_conflito():
    f = mesclar_fatos({"capacidade_bateria_kwh": 60, "soc_atual_pct": 25}, {"soc_alvo_pct": 80})
    assert f == {"capacidade_bateria_kwh": 60, "soc_atual_pct": 25, "soc_alvo_pct": 80}
    f2 = mesclar_fatos(f, {"soc_atual_pct": 90})       # novo atual > alvo antigo -> alvo cai
    assert "soc_alvo_pct" not in f2 and f2["soc_atual_pct"] == 90
