# Tabela de versões do system prompt

Exigência do §6 do enunciado: *"System prompt versionado — tabela de versões com
o que mudou, por quê e o ganho medido."*

Cada linha só é preenchida **depois** de rodar o eval. Nenhuma versão entra aqui
com ganho estimado ou esperado — se não foi medido, fica em branco.

| Versão | Arquivo | Tokens | O que mudou | Por quê | Ganho medido |
|---|---|---|---|---|---|
| legado | `ai/prompts/system_prompt.txt` + `few_shots.txt` + `goodwe_context.py` | ~4.450 | — (linha de base) | versão manual das Sprints 1/2 | nota 1.0 · conformidade 32.1% · 5.033 tokens/turno |
| — | *(sem prompt versionado)* | 0 | chain LCEL com system genérico de 2 linhas | isolar o efeito do **framework** do efeito do **prompt** | nota 1.5 · conformidade 35.7% · 400 tokens/turno |
| **v1** | `prompts/system_prompt_v1.md` | **641** | identidade travada; escopo explícito; três limites de domínio com encaminhamento obrigatório a profissional habilitado; regra de não inventar especificação; uso obrigatório do perfil; limite de formato | as falhas do baseline foram **medidas**, não supostas: `dominio_restrito` em **0%**, `fora_de_escopo` em 33%, e verbosidade estourando o teto no S12-03 | **nota 1.707 · conformidade 67.9% · 1.373 tokens/turno · 1.141 ms** |
| v2 | `prompts/system_prompt_v2.md` | | XML tagging (Aula 04); formato apertado para 3–4 frases; bloco de fatos do domínio (queda de potência acima de 80%, eficiência típica); restrição financeira reduzida ao seu alvo real | o v1 deixou o formato frouxo (6–8 frases) enquanto o eval cobra 3–4: **7 casos** reprovaram só por `prolixo`. E a regra financeira ampla fez o EC-05 recusar uma pergunta legítima sobre custo comparado | *(preencher)* |

## Resultado consolidado do eval (28 casos, `gpt-oss:120b`, 09/09)

| Coluna | Nota | Conformidade | Tokens/turno | Latência |
|---|---|---|---|---|
| Legado (manual, Sprints 1/2) | 1.119 | 28.6% | 5.004 | 3.562 ms |
| LCEL cru (só o framework) | 1.000 | 35.7% | 915 | 4.349 ms |
| **LCEL v1 (framework + prompt)** | **1.707** | **67.9%** | 1.373 | **1.141 ms** |

O achado que justifica a coluna do meio: **o framework sozinho não melhorou a
nota** (1.119 → 1.000). O ganho veio do prompt versionado (1.000 → 1.707). Sem
essa coluna, o relatório atribuiria ao LangChain um mérito que é do trabalho de
context engineering.

## Como cada número foi obtido

- **Tokens do prompt**: `python -c "from src.chain.builder import resumo_versao; print(resumo_versao('v1'))"`
- **Nota, conformidade, tokens/turno**: `evals/resultados/*.json`, campo `metricas`
- **Régua de tokens**: `tiktoken/cl100k_base` para tudo. Não é o tokenizador do
  gpt-oss, então o valor absoluto é aproximado — mas é a **mesma** régua em
  todas as linhas, que é o que a comparação exige.

## Nota de método

O front matter entre `---` no topo de cada `.md` é metadado para humanos e é
removido pelo carregador antes de ir ao modelo. Sem isso, a justificativa da
versão entraria no prompt e ainda seria contada como token — inflando a própria
métrica que a tabela pretende medir.
