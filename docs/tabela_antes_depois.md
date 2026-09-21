# Tabela antes/depois — Sprint 03 (§8, obrigatória)

Gerada automaticamente em 2026-09-20T23:05:49 por `evals/gerar_relatorios.py` a partir de `evals/resultados/`. Modelo: `gpt-oss:120b`. Mesmo eval set (28 casos, v1.1), mesma régua de pontuação (v1.1), mesmo juiz, mesmo runner para todas as colunas.

| Métrica | Sprints 1/2 (manual/legado) | LCEL cru (só framework) | Sprint 03 LCEL + prompt v1 | Sprint 03 LCEL + prompt v2 (final) |
|---|---|---|---|---|
| Qualidade — nota do juiz (0 a 2, ponderada) | pendente | pendente | pendente | pendente |
| Qualidade — conformidade determinística | pendente | pendente | pendente | pendente |
| Tokens por turno (tiktoken o200k_harmony) | pendente | pendente | pendente | pendente |
| Tokens por turno reais do servidor (inclui raciocínio) | pendente | pendente | pendente | pendente |
| Chamadas ao LLM por turno | pendente | pendente | pendente | pendente |
| Latência média (ms) | pendente | pendente | pendente | pendente |
| Latência p90 (ms) | pendente | pendente | pendente | pendente |
| Structured output — acurácia por campo | pendente | n/a | n/a | pendente |
| Structured output — schema válido | pendente | n/a | n/a | pendente |
| Turnos resolvidos pelos guardrails (sem LLM) | pendente | pendente | pendente | pendente |
| Tokens fixos do system prompt | 3700 | ~40 | 307 | 987 |
| Guardrails: bloqueio / falso positivo | não havia | não havia | 100.0% / 0.0% | 100.0% / 0.0% |

Leitura das colunas: *legado → LCEL cru* isola o efeito do framework; *LCEL cru → v1/v2* isola o efeito de prompt, structured output e guardrails.

Notas de método:
- Structured output do legado: o Sprint 2 não tinha saída estruturada. A coluna mede o caminho manual equivalente (LLMProvider do legado + `json.loads`), ver `evals/structured_eval.py`.
- Tokens: régua única `o200k_harmony` (tokenizador do gpt-oss) para todas as colunas; a linha "reais do servidor" vem de `usage_metadata`/`eval_count` do Ollama.
- Ablação (v2 sem guardrails): nota do juiz (0 a 2, ponderada): pendente, conformidade determinística: pendente, Latência média (ms): pendente.
