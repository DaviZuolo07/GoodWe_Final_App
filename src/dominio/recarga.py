"""
Calculadora determinística de recarga.

O LLM nunca faz esta conta. Ele extrai os parâmetros (`ConsultaRecarga`), este
módulo calcula, e o resultado entra no contexto do redator como
<calculo_verificado>. Número que o usuário lê saiu daqui, não do modelo.

FUNDAMENTAÇÃO (ver docs/fundamentacao_calculos.md)
--------------------------------------------------
Eficiência de recarga AC = energia que entra na bateria / energia da rede.

  central 0,894  Sears, Roberts & Glitman (2014), IEEE SusTech, pp. 255-258:
                 média medida de recargas Nível 2 (240 V) = 89,4%.
  pior    0,857  mesmo estudo: média geral de 115 recargas (N1 + N2) = 85,7%.
  melhor  0,920  eficiência de carregadores AC de 16-22 kW medida entre
                 91,6% e 92,2% (compilado por Recurrent, 2022).

  O intervalo não é enfeite: a eficiência cai em recargas curtas e em
  temperaturas extremas (mesmo estudo). Dar um número só seria precisão falsa.

Curva CC-CV (DC): baterias de íon-lítio carregam em corrente constante até
~80% e depois em tensão constante, com a corrente decaindo. Em AC residencial a
potência (7-22 kW) é baixa perto da capacidade de aceitação da bateria e o
efeito é pequeno; em DC ele domina o fim da recarga. Por isso a desaceleração
acima de 80% só entra no limite superior do DC, como premissa explícita.

Energia:  E_bateria = C x (alvo - atual) / 100
          E_rede    = E_bateria / eficiência
Potência: P_efetiva = min(P_carregador, P_max_AC_do_veículo)   (AC)
Tempo:    t = E_rede / P_efetiva
Custo:    custo = E_rede x tarifa        (tarifa NUNCA é inventada)
"""

from __future__ import annotations

from src.schemas.consulta_recarga import ConsultaRecarga
from src.schemas.resultados import CalculoRecarga

EFICIENCIA_AC = {"central": 0.894, "min": 0.857, "max": 0.920}
# DC: sem estudo de referência no projeto -> premissa conservadora declarada.
EFICIENCIA_DC = {"central": 0.90, "min": 0.88, "max": 0.93}

SOC_INICIO_CV = 80.0          # início típico da fase de tensão constante
FATOR_POTENCIA_CV_DC = 0.5    # premissa: acima de 80% o DC entrega ~metade


def _r(x: float | None, casas: int = 2) -> float | None:
    return None if x is None else round(x, casas)


def horas_para_texto(h: float) -> str:
    """7.256 -> '7h15' (arredondado ao minuto)."""
    minutos = int(round(h * 60))
    return f"{minutos // 60}h{minutos % 60:02d}"


def calcular(consulta: ConsultaRecarga) -> CalculoRecarga:
    faltantes = consulta.faltantes_para_tempo()
    if faltantes:
        return CalculoRecarga(status="dados_insuficientes", faltantes=faltantes)

    c = consulta
    dc = c.tipo_corrente == "DC"
    efic = EFICIENCIA_DC if dc else EFICIENCIA_AC
    premissas: list[str] = []

    p_ef = c.potencia_carregador_kw
    if not dc and c.potencia_max_ac_veiculo_kw:
        if c.potencia_max_ac_veiculo_kw < p_ef:
            premissas.append(
                f"potência limitada pelo carregador de bordo do veículo "
                f"({c.potencia_max_ac_veiculo_kw:g} kW), não pelo carregador ({p_ef:g} kW)"
            )
        p_ef = min(p_ef, c.potencia_max_ac_veiculo_kw)

    e_bat = c.capacidade_bateria_kwh * (c.soc_alvo_pct - c.soc_atual_pct) / 100.0

    def tempo(eta: float, com_cv: bool) -> float:
        p_bat = p_ef * eta                                  # kW que chegam à bateria
        t = e_bat / p_bat
        if com_cv and c.soc_alvo_pct > SOC_INICIO_CV:
            faixa = c.soc_alvo_pct - max(c.soc_atual_pct, SOC_INICIO_CV)
            e_cv = c.capacidade_bateria_kwh * faixa / 100.0
            t += (e_cv / p_bat) * (1 / FATOR_POTENCIA_CV_DC - 1)
        return t

    t_central = tempo(efic["central"], com_cv=False)
    t_min = tempo(efic["max"], com_cv=False)
    t_max = tempo(efic["min"], com_cv=dc)

    e_rede = e_bat / efic["central"]
    premissas.append(
        f"eficiência de recarga {'DC' if dc else 'AC'} de {efic['central']:.1%} "
        f"(faixa {efic['min']:.1%} a {efic['max']:.1%})".replace(".", ",")
    )
    if dc and c.soc_alvo_pct > SOC_INICIO_CV:
        premissas.append("em DC, acima de 80% a potência cai (fase CV); incluído no limite superior")
    elif not dc and c.soc_alvo_pct > 90:
        premissas.append("os últimos pontos percentuais podem ser um pouco mais lentos")

    custo = custo_min = custo_max = None
    if c.tarifa_kwh_brl:
        custo = e_rede * c.tarifa_kwh_brl
        custo_min = e_bat / efic["max"] * c.tarifa_kwh_brl
        custo_max = e_bat / efic["min"] * c.tarifa_kwh_brl
    else:
        premissas.append("custo não calculado: tarifa não informada")

    return CalculoRecarga(
        status="ok",
        energia_bateria_kwh=_r(e_bat),
        energia_rede_kwh=_r(e_rede),
        potencia_efetiva_kw=_r(p_ef),
        tempo_central_h=_r(t_central, 3),
        tempo_min_h=_r(t_min, 3),
        tempo_max_h=_r(t_max, 3),
        custo_brl=_r(custo),
        custo_min_brl=_r(custo_min),
        custo_max_brl=_r(custo_max),
        premissas=premissas,
    )


def _br(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def renderizar(calc: CalculoRecarga | None, consulta: ConsultaRecarga | None = None) -> str:
    """Bloco de texto que o redator recebe em <calculo_verificado>."""
    if calc is None:
        return "nenhum cálculo necessário nesta mensagem"
    if calc.status == "dados_insuficientes":
        return ("dados insuficientes para estimar. Peça ao usuário, numa única frase: "
                + "; ".join(calc.faltantes))
    linhas = [
        f"energia a repor na bateria: {_br(calc.energia_bateria_kwh)} kWh",
        f"energia retirada da rede (com perdas): {_br(calc.energia_rede_kwh)} kWh",
        f"potência efetiva: {_br(calc.potencia_efetiva_kw)} kW",
        f"tempo estimado: {horas_para_texto(calc.tempo_central_h)} "
        f"(faixa {horas_para_texto(calc.tempo_min_h)} a {horas_para_texto(calc.tempo_max_h)})",
    ]
    if calc.custo_brl is not None:
        linhas.append(
            f"custo estimado: R$ {_br(calc.custo_brl, 2)} "
            f"(faixa R$ {_br(calc.custo_min_brl, 2)} a R$ {_br(calc.custo_max_brl, 2)})"
        )
    linhas.append("premissas: " + "; ".join(calc.premissas))
    return "\n".join(linhas)
