# Rubrica manual (fallback do RAGAS) — critérios e equivalência

O §8 do enunciado aceita uma rubrica manual 0–1 no lugar do RAGAS, desde que seja
documentada, aplicada no mesmo eval set a cada iteração e tenha a equivalência
justificada. Neste projeto o RAGAS **funcionou** (Python 3.13, `ragas==0.4.3`), e a
rubrica roda **junto**, na mesma execução (`python -m evals.ragas_eval`), por dois
motivos: se o RAGAS quebrar, o número das duas iterações já existe na mesma régua; e as
duas medidas lado a lado mostram quando uma delas erra (ver "Divergências medidas").

Implementação: `evals/juiz_rag.py`. Prompts no formato da Aula 07 (slide "Fallback —
RAGAS manual").

## Juiz

| Item | Valor | Por quê |
|---|---|---|
| Modelo | `gpt-oss:120b` (`MODELO_JUIZ` no `.env`) | o mesmo nas duas iterações: trocar o juiz é trocar a régua |
| Perfil | `classificador`: temperature 0, top_p 1, seed 42 | nota reprodutível |
| Saída inválida | `-1.0` (sentinela da Aula 07), excluída da média | o modelo às vezes devolve texto junto do número; `ler_nota` extrai o primeiro número entre 0 e 1 antes de desistir |
| Fallback de transporte | `get_llm_robusto` (sem `think`, dobro de tokens) se a resposta vier vazia | resposta vazia é falha de transporte, não nota 0 |

## Critério 1 — fidelidade (equivale a `faithfulness`)

Pergunta ao juiz: a RESPOSTA está fundamentada no CONTEXTO (os trechos que o modelo recebeu)?

| Nota | Critério |
|---|---|
| 1.0 | toda a resposta está no contexto |
| 0.5 | resposta parcialmente no contexto |
| 0.0 | a resposta inventa informação que não está no contexto |

Citações `(fonte: documento, página X)` não contam como afirmação. Resposta que é a
recusa literal não recebe nota de fidelidade (não afirma nada).

**Equivalência.** O `faithfulness` do RAGAS decompõe a resposta em afirmações e calcula a
fração sustentada pelo contexto (Es et al., 2024; Aula 07, slide de interpretação). A
rubrica pede ao juiz o mesmo julgamento de uma vez, em três degraus em vez de contínuo:
1.0 corresponde a "todas as afirmações sustentadas", 0.0 a "alguma afirmação inventada que
domina a resposta", 0.5 ao meio. A pergunta é a mesma (alucinação em relação ao contexto
recuperado), mas a resolução é mais grossa.

## Critério 2 — relevância (equivale a `answer_relevancy`)

Pergunta ao juiz: a RESPOSTA aborda diretamente o que a PERGUNTA pediu? (não julga se é
verdade)

| Nota | Critério |
|---|---|
| 1.0 | responde diretamente e por completo ao que foi perguntado |
| 0.5 | responde em parte, ou com desvio de foco |
| 0.0 | não responde (recusa, evasiva ou outro assunto) |

**Equivalência.** O `answer_relevancy` do RAGAS gera perguntas a partir da resposta e mede
a similaridade de embedding com a pergunta original; recusa ("noncommittal") vale 0. A
rubrica avalia diretamente a mesma propriedade, inclusive punindo a recusa com 0.

## Mesma régua nas iterações

Eval set `evals/eval_set_rag.json` (congelado), juiz e perfil fixos, embeddings
`nomic-embed-text`, tokenizador `o200k_harmony`. Os dois critérios são aplicados só aos 14
casos respondíveis; os 2 casos de recusa são medidos pela checagem determinística
`recusa_correta`.

## Divergências medidas entre a rubrica e o RAGAS

- **A rubrica é mais generosa em relevância.** Na iteração 1, R02 ("quanto tempo de
  tolerância se eu me atrasar?") foi respondida com o artigo vizinho do regimento (30
  minutos para retirar o carro, em vez de 15 minutos de tolerância). O juiz manual deu 1.0
  de relevância; o RAGAS deu 0,68. A rubrica de 3 degraus não pega "respondeu a uma
  pergunta parecida". Por isso o RAGAS é a métrica principal do relatório, e a rubrica
  fica como fallback e conferência.
- **Régua 0 (descartada).** Na primeira execução, o contexto entregue ao RAGAS era o
  texto cru do trecho, sem o rótulo `[documento, página]` que o modelo recebe no prompt. O
  RAGAS tratou a citação `(fonte: …, página 2)` como afirmação sem suporte e deu 0,5 a
  respostas certas com uma citação. A rubrica, que manda ignorar citação, deu 1.0. A régua
  foi corrigida (contexto rotulado) e a iteração 1 reexecutada; o arquivo da régua 0 fica
  em `evals/resultados/ragas_1-regua0_*.json` como registro.
