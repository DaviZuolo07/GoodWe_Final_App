# Relatório de mudanças — Sprint 03

Ponto de partida: `GoodWe_Final_App.zip` (31/08). Ele tinha `src/chain/llm.py`, `hello_lcel.py`,
diagnóstico, eval set com 5 casos `PREENCHER`, `AdaptadorLegado` não implementado e um único
resultado real (`lcel_cru`, 5 casos). **`ai/` (Sprint 2) não foi alterado** — é o grupo de controle.

## Mapa contrato → implementação

| Contrato | Arquivo | Status |
|---|---|---|
| §3.1 Chain LCEL end-to-end | `src/chain/builder.py` | ✅ `prompt \| ChatOllama \| StrOutputParser` + `RunnableBranch` + `RunnablePassthrough.assign` |
| §3.2 Memória por sessão, limite de tokens, 3+ turnos | `src/chain/memoria.py`, `evals/memoria_demo.py` | ✅ 6 turnos, poda demonstrada |
| §3.3 Pydantic v2 com field_validator | `src/schemas/consulta_recarga.py` | ✅ 5 field_validators + model_validator |
| §3.4 Prompt versionado XML + tiktoken | `prompts/system_prompt_v1.md`, `v2.md`, `src/chain/tokens.py` | ✅ |
| §3.5 Guardrails | `src/guardrails/moderation.py`, `scope_validator.py` | ✅ 39/39, 0/44 FP |
| §5 pastas exigidas | `prompts/`, `src/chain/`, `src/schemas/`, `src/guardrails/`, `evals/`, `docs/` | ✅ |
| §5 `sprint3_results.json` | `evals/sprint3_results.json` (gerado) | ✅ |
| §6 tabela de versões com ganho | `prompts/README.md` (gerado) | ✅ estrutura; ganho após execução |
| §6 relatorio_modelos.md (2+ modelos, parâmetros) | `docs/relatorio_modelos.md` (gerado) | ✅ estrutura; números após execução |
| §8 relatório ≤5 páginas com tabela antes/depois | `docs/relatorio_evolucao.pdf` (gerado, 2 págs) | ✅ estrutura; números após execução |
| Bônus multi-provider | `src/chain/multi_provider.py` | ✅ |

## Arquivos novos

| Arquivo | O que faz |
|---|---|
| `src/chain/tokens.py` | Régua única **o200k_harmony** (tokenizador real do gpt-oss); contagem por mensagem com overhead do formato de chat; `ids()` injetado no ChatOllama para a memória contar tokens offline. |
| `src/chain/prompts.py` | Carrega `prompts/system_prompt_vN.md` (cabeçalho + corpo), monta `ChatPromptTemplate` com `MessagesPlaceholder("historico")`, injeta base de produtos e **canário** via `.partial()`, mede tokens do legado e de cada versão. |
| `src/chain/builder.py` | `ChatbotChargeOps`: pipeline LCEL completo, extração estruturada com **autocorreção** (devolve o erro de validação ao modelo 1 vez), cálculo, memória, validação de saída, telemetria de tokens (régua + `usage_metadata` do servidor). |
| `src/chain/memoria.py` | `HistoricoComLimiteDeTokens`: adapta `ConversationTokenBufferMemory` para `RunnableWithMessageHistory` usando a poda da própria classe. `RepositorioSessoes` (multiusuário, thread-safe). Política de resumo **estruturada**: fatos validados sobrevivem à janela. |
| `src/chain/multi_provider.py` | Bônus: matriz modelo × prompt em um `RunnableParallel`; prefixo `local:` = 2º provedor. |
| `src/schemas/consulta_recarga.py` | `ConsultaRecarga` (12 campos, `Literal`, faixas `gt/le`), validators pt-BR ("7,4 kW", "R$ 2,10", "livre"→disponivel), `mesclar_fatos`, `instrucoes_compactas` (−52% tokens). |
| `src/schemas/resultados.py` | `CalculoRecarga`, `VereditoJuiz`, `RespostaTurno`. |
| `src/dominio/recarga.py` | Calculadora determinística com eficiência de estudo (89,4%, faixa 85,7–92%), limite do carregador de bordo, faixa de tempo e custo. |
| `src/guardrails/moderation.py` | Injeção, jailbreak, escalação de privilégio/dados de terceiros, fraude de medição; normalização contra leetspeak, letras espaçadas, invisíveis e base64. |
| `src/guardrails/scope_validator.py` | Emergência, segurança elétrica (NBR 5410/17019), jurídico, financeiro, produto fora da base, fora de escopo; validador de saída (canário, tags internas, bitola/disjuntor). |
| `src/app.py` | Chat no terminal com `/memoria`, `/extrair`, `/limpar`, `--detalhes`, `--trace`, `--perfil-demo`. |
| `src/ui/streamlit_app.py` | Interface Streamlit da Sprint 03 (7 painéis) com a identidade visual do painel ChargeOps; demonstra e testa chain, memória, extração, guardrails, tokens, multi-provider e eval. |
| `docs/AUDITORIA_SPRINT3.md` | Auditoria contra o contrato e as aulas, com 8 achados corrigidos e riscos residuais declarados. |
| `prompts/system_prompt_v1.md`, `v2.md`, `base_produtos.json` | Prompts versionados e única fonte de especificação de produto. |
| `evals/structured_eval.py` + `structured_set.json` | Acurácia do structured output: 15 casos com gabarito, manual × LCEL. |
| `evals/guardrails_eval.py` + `guardrails_set.json` | 39 ataques/restritos + 44 legítimas; roda offline. |
| `evals/memoria_demo.py` | Demonstração de 6 turnos com checagem de coerência e `load_memory_variables()`. |
| `evals/executar_tudo.py` | Bateria completa em um comando. |
| `evals/gerar_relatorios.py`, `relatorio_pdf.py` | Gera `sprint3_results.json`, tabela antes/depois, relatório de modelos, tabela de versões e o PDF — **só a partir de resultados medidos**. |
| `tests/` (122 testes) + `servidor_ollama_falso.py` | Testes offline e servidor falso para ensaiar a fiação sem cota. |
| `docs/COMO_TESTAR.md`, `fundamentacao_calculos.md`, `equipe.json`, `.env.example` | Fluxo de teste, fontes dos cálculos, equipe (preencher), variáveis de ambiente. |

## Arquivos alterados

| Arquivo | Mudança | Por quê |
|---|---|---|
| `src/chain/llm.py` | `num_predict` 400→1024; `seed`; `think` só para modelos de raciocínio; `get_llm_robusto` com `with_fallbacks`; prefixo de provedor; `custom_get_token_ids` | respostas vazias por orçamento gasto no raciocínio; gemma/glm vazios com `think`; bônus multi-provider |
| `evals/adaptadores.py` | `AdaptadorLegado` implementado (troca só o transporte: auth + host); novo `AdaptadorLCEL` | coluna "antes" real, sem mexer em `ai/` |
| `evals/runner.py` | mede tokens de todas as chamadas + tokens reais do servidor, p90, rota, structured; `--prompt`, `--papel`, `--sem-guardrails` | métricas do §8 e ablação |
| `evals/pontuacao.py` | v1.1: termo curto só isolado ("h" casava com tudo), listas contam como frases, marcadores de recusa | régua dava falso acerto |
| `evals/juiz.py` | saída validada com Pydantic (`VereditoJuiz`), sem `think`, 1 retentativa | glm-flash devolvia vazio; nota inválida vira None, nunca chute |
| `evals/eval_set.json` | v1.1: S12-01..05 preenchidos **literalmente** de `docs/test_cases.md`; campo `perfil` | §8 exige o mesmo eval das Sprints 1/2 (placeholders nunca executados) |
| `src/diagnostico.py` | tiktoken pela régua nova; tabela de parâmetros lida de `PERFIS` | docs/ambiente.md estava desatualizado |
| `requirements-sprint3.txt` | + requests, reportlab, pytest (fixados) | legado, PDF, testes |
| `README.md` | seção Sprint 03 no topo; documentação Sprint 2 preservada | |

## Medições já reais (independem de chave de API)

| Medida | Valor |
|---|---|
| Tokens fixos por chamada: legado → v1 → v2 | 3.700 → 307 → 989 (o200k_harmony) |
| Instrução de formato Pydantic: padrão → compacta | 1.060 → 508 tokens |
| Guardrails: bloqueio / falso positivo / encaminhamento | 39/39 · 0/44 · 11/11 |
| Casos do eval resolvidos sem LLM | 14 de 28 |
| Turno médio da Sprint 2 (base do limite de memória) | 174 tokens → 1200 cobre ≈6,9 turnos |
| Testes offline | 122 passando |

## O que depende de execução na máquina do grupo

Nota do juiz, conformidade, latência, tokens reais do servidor, acurácia do structured output e
comparação entre modelos. O ambiente onde o código foi escrito não acessa a ollama.com, então
**nenhum desses números foi estimado**: as células ficam "pendente" até `python -m evals.executar_tudo`.

## Limites conhecidos (declarados, não escondidos)

- Guardrails por regra não cobrem paráfrase criativa infinita; o prompt v2 (spotlighting + canário) e o validador de saída são as camadas seguintes. As 44 perguntas legítimas foram escritas junto com as regras: o 0% de falso positivo tem esse viés.
- `ConversationTokenBufferMemory` poda mensagem a mensagem; a janela pode ficar com número ímpar de mensagens (comportamento da própria classe).
- `ConversationTokenBufferMemory` e `RunnableWithMessageHistory` são deprecated no LangChain 1.x (sugerem LangGraph, Módulos 3/4); usadas porque o escopo exige.
- Eficiência DC e desaceleração acima de 80% em DC são premissas declaradas, não medidas.
- Embeddings/RAG não foram incluídos: o §3 os marca como fora do escopo desta sprint (CKP02).
