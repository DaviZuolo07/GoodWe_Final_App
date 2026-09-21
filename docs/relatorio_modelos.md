# Relatório de uso de modelos e parâmetros (§6)

Gerado em 2026-09-20T23:05:49 a partir de `evals/resultados/`. Execução: `python -m evals.executar_tudo`.

## 1. Modelos comparados

| Papel | Modelo | Provedor | Raciocínio (`think`) |
|---|---|---|---|
| principal | `gpt-oss:120b` | local (http://127.0.0.1:11434) | low |
| comparacao | pendente: defina `OLLAMA_MODEL_B` no .env | | |

Juiz do eval: `glm-5.3-flash` (ou `MODELO_JUIZ`), propositalmente FORA da lista acima para evitar viés de auto-preferência.

## 2. Parâmetros (temperature, top_p, max_tokens)

Definidos em `src/chain/llm.py` (`PERFIS`). `num_predict` é o max_tokens do Ollama.

| Perfil | temperature | top_p | max_tokens | seed | Uso e justificativa |
|---|---|---|---|---|---|
| `classificador` | 0.0 | 1.0 | 512 | 42 | contagem de tokens da memória e roteamento; reprodutível |
| `redator` | 0.2 | 0.9 | 1024 | 42 | resposta ao usuário; 0,2 dá texto natural sem floreio numérico (acima de ~0,4 o modelo arredonda/inventa número) |
| `estruturado` | 0.0 | 1.0 | 1024 | 42 | extração Pydantic e juiz; zero criatividade, JSON válido de primeira |

Legado (Sprint 2): não enviava parâmetro nenhum (usava os padrões do modelo e raciocínio padrão). Isso é parte do que a coluna "antes" mede.

Por que max_tokens alto (1024): no Ollama, `num_predict` conta também os tokens de raciocínio do gpt-oss. Com 400 tokens e `think=low`, parte das respostas saía vazia. A concisão passou a ser controlada pelo prompt (`<formato>`: no máximo 4 frases), e o fallback `with_fallbacks` repete a chamada sem `think` e com o dobro do orçamento se vier vazio.

## 3. Resultados por modelo (LCEL + prompt v2, mesmo eval de 28 casos)

| Modelo | Nota juiz | Conformidade | Latência média | Latência p90 | Tokens servidor/turno | Structured (acurácia) |
|---|---|---|---|---|---|---|
| `gpt-oss:120b` | pendente | pendente | pendente | pendente | pendente | pendente |

### Por categoria (nota média do juiz)

| Modelo | happy_path | edge_case | jailbreak | fora_de_escopo | dominio_restrito |
|---|---|---|---|---|---|
| `gpt-oss:120b` | pendente | pendente | pendente | pendente | pendente |

## 4. Conclusão

Pendente: rode `python -m evals.executar_tudo` com `OLLAMA_MODEL_B` definido.

## 5. Contexto e memória

Tokens fixos do system prompt: legado 3700 → v1 307 → v2 987 (régua `o200k_harmony`). Instrução de formato do structured output: `get_format_instructions()` = 1060 tokens; versão compacta gerada do mesmo schema = 508 tokens.

`max_token_limit` da memória = 1200. Justificativa medida: as 5 conversas registradas da Sprint 2 (docs/test_cases.md) têm média de 21 tokens por pergunta e 144 por resposta, ≈174 tokens por turno com overhead; 1200 tokens guardam ≈6,9 turnos completos. Com o limite de 4 frases do prompt v2 as respostas encolhem e a janela cobre mais turnos. Fica dentro da faixa 800–1500 recomendada na Aula 02.


## 6. Observações de compatibilidade (medidas no projeto)

- `gemma4` e `glm-*-flash` devolvem conteúdo vazio quando recebem o campo `think`: a fábrica só envia `think` para famílias de raciocínio (gpt-oss, qwen3, kimi, deepseek, nemotron).
- Sufixo `-cloud` é para o Ollama local puxar da nuvem; falando direto com ollama.com o nome é sem sufixo (senão 404).
- `GET /api/tags` da ollama.com é público; só `POST /api/chat` valida a chave (falso verde do 1º diagnóstico).
- Contagem com `o200k_harmony` é exata para o gpt-oss e aproximada para os demais modelos; todos são medidos com a mesma régua.
