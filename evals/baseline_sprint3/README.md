# Linha de base congelada (Sprint 3)

Resultados **medidos com modelo real** antes da Sprint 04. São a coluna "antes"
da tabela antes/depois do relatório de evolução. Não editar.

| Arquivo | O que é |
|---|---|
| `legado[...]_093117.json`, `legado[...]_105455.json` | versão original (Sprints 1/2, código `ai/`) |
| `lcel_cru[...].json` | chain LCEL sem prompt versionado (gpt-oss:120b e gemma4:31b) |
| `lcel_v1[...].json` | LCEL + system prompt v1 (2 execuções) |
| `guardrails_20260920_224715.json` | eval determinístico dos guardrails: 39/39 bloqueados, 0 falsos positivos |

O código que gerou esses arquivos (legado `ai/`, runner, juiz, adaptadores) foi
removido na Sprint 04 e continua disponível na tag Git `sprint3-final`:

    git checkout sprint3-final -- ai/        # traz o legado de volta, se precisar remedir
