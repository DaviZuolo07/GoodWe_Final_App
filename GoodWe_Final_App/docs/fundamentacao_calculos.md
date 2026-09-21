# Fundamentação dos cálculos de recarga

Implementação: `src/dominio/recarga.py`. O LLM nunca faz estas contas; ele só extrai os
parâmetros (`ConsultaRecarga`) e narra o resultado que recebe em `<calculo_verificado>`.

## Fórmulas

| Grandeza | Fórmula |
|---|---|
| Energia que entra na bateria | E_bat = C × (alvo − atual) / 100 |
| Energia retirada da rede | E_rede = E_bat / η |
| Potência efetiva (AC) | P_ef = min(P_carregador, P_máx AC do veículo) |
| Tempo | t = E_rede / P_ef = E_bat / (P_ef × η) |
| Custo | custo = E_rede × tarifa (a tarifa **nunca** é inventada) |

## Eficiência de recarga (η)

| Valor | Uso | Fonte |
|---|---|---|
| 0,894 | central (AC) | Sears, Roberts & Glitman (2014), *A comparison of electric vehicle Level 1 and Level 2 charging efficiency*, IEEE SusTech, pp. 255–258, DOI 10.1109/SusTech.2014.7046253 — média medida de recargas Nível 2 = 89,4% |
| 0,857 | pior caso | mesmo estudo — média geral de 115 recargas (N1 + N2) = 85,7% |
| 0,920 | melhor caso | eficiência de carregadores AC de 16–22 kW medida entre 91,6% e 92,2% (compilado Recurrent, 2022) |

O mesmo estudo mostra que a eficiência cai em recargas curtas e em temperaturas extremas.
Por isso o sistema entrega **faixa**, não número único: precisão maior do que a física
permite seria falsa.

## Curva de carga (CC-CV)

Íon-lítio carrega em corrente constante até ~80% e depois em tensão constante, com a
corrente caindo. Em AC residencial (7–22 kW) a potência é baixa em relação à capacidade de
aceitação da bateria, e o efeito é pequeno. Em DC ele domina o fim da recarga. Assim:

- AC: sem desaceleração no cálculo; nota qualitativa acima de 90%.
- DC: faixa superior assume potência média de 50% acima de 80% — **premissa declarada**,
  não medida no projeto (eficiência DC 0,88–0,93 também é premissa).

## Conferência manual (também está em `tests/test_schema_e_calculo.py`)

| Caso | Conta | Resultado |
|---|---|---|
| 60 kWh, 20→100%, 7,4 kW | 48 / (7,4 × 0,894) | 7,256 h = **7h15** (faixa 7h03–7h34) |
| Sprint 2, caso 2: 44,9 kWh, 20→100%, 7,4 kW | 35,92 / 6,6156 | **5h26** (a Sprint 2 respondeu "5h30 a 6h") |
| mesmo caso, tarifa R$ 2,10 | 35,92 / 0,894 × 2,10 | **R$ 84,38** |
| 60 kWh, 25→80%, 7,4 kW | 33 / 6,6156 | 4,988 h = 4h59 |

## Base de produtos

`prompts/base_produtos.json` vem do seed do condomínio de demonstração. Conferência física:
7,4 kW = 230 V × 32 A (monofásico: 7,36 kW); 22 kW = √3 × 400 V × 32 A (trifásico: 22,17 kW).

## Normas citadas nas recusas de segurança elétrica

ABNT NBR 5410 (instalações de baixa tensão) e ABNT NBR 17019:2022 (instalações em locais
especiais — alimentação de veículos elétricos, baseada na IEC 60364-7-722).
