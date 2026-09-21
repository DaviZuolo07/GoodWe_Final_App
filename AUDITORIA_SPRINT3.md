# Auditoria técnica — Sprint 03

Revisão do projeto contra o documento oficial do Challenge (Sprint 03, versão 1.0) e o
conteúdo das Aulas 01 a 04 do Módulo 1. Método: leitura do contrato item a item, execução
dos artefatos, análise estática (`pyflakes`) e suíte de 122 testes.

Data da auditoria: 20/09/2026 · Auditor: revisão técnica do código entregue.

---

## 1. Escopo exigido (§3 do contrato)

| # | Exigência | Evidência | Situação |
|---|---|---|---|
| 1 | Chain LCEL end-to-end: `ChatPromptTemplate \| ChatOllama (gpt-oss:120b) \| parser` | `src/chain/builder.py::montar_chain_resposta`; modelo em `src/chain/llm.py` (`OLLAMA_MODEL=gpt-oss:120b`) | ✅ |
| 2 | `RunnableWithMessageHistory` + `ConversationTokenBufferMemory`, limite de tokens, 3+ turnos | `src/chain/memoria.py`; demo de 6 turnos em `evals/memoria_demo.py`; teste `test_memoria_poda_e_fatos_sobrevivem` | ✅ |
| 3 | Schema Pydantic v2 do domínio EV com `field_validator` (ex.: `ConsultaRecarga`) | `src/schemas/consulta_recarga.py`: 5 `field_validator` + 1 `model_validator`; nome do schema igual ao sugerido no contrato | ✅ |
| 4 | System prompt versionado (XML tagging) + medição com tiktoken | `prompts/system_prompt_v1.md` e `v2.md` (v2 com XML); `src/chain/tokens.py` | ✅ |
| 5 | Segurança e guardrails: jailbreak/injection + escopo GoodWe | `src/guardrails/`; eval offline 39/39 bloqueios, 0/44 falso positivo | ✅ |
| 6 | Relatório de evolução (até 5 páginas) com tabela antes/depois | `evals/relatorio_pdf.py` → `docs/relatorio_evolucao.pdf` (2 páginas) | ✅ estrutura; números após execução com chave |

### Itens marcados como NÃO obrigatórios

LangGraph, agentes, function calling, RAG, interface web e observabilidade pertencem aos
Módulos 3 e 4. Nenhum deles entrou no núcleo avaliado:

- **LangGraph**: só permanece fixado em `requirements-sprint3.txt` (não é importado por nenhum módulo).
- **RAG/embeddings**: ausente de propósito. É conteúdo do CKP02, entregue na mesma data mas **separado**.
- **Interface web**: `src/ui/streamlit_app.py` existe como ferramenta de demonstração e teste. Não substitui nada da chain — ela chama o mesmo `ChatbotChargeOps` do terminal. Está declarado como extra, não como cumprimento de item.

---

## 2. Pontos obrigatórios (§6)

| Exigência | Onde | Situação |
|---|---|---|
| System prompt versionado com tabela de versões (o que mudou, por quê, ganho medido) | `prompts/README.md`, gerado por `evals/gerar_relatorios.py` | ✅ estrutura e tokens medidos; colunas de ganho preenchem ao rodar o eval |
| `relatorio_modelos.md` comparando 2+ modelos com temperature, top_p e max_tokens | `docs/relatorio_modelos.md` | ✅ parâmetros documentados; métricas por modelo após execução |
| Não inventar especificação de produto fora da base | `prompts/base_produtos.json` + regra `especificacao_fora_da_base` | ✅ testado (`test_spec_fora_da_base_nao_ecoa_numeros`) |
| Recusa jurídica, financeira e de segurança elétrica com encaminhamento a profissional | `src/guardrails/scope_validator.py` | ✅ 11/11 recusas citam profissional habilitado |
| Recusa de jailbreak e prompt injection | `src/guardrails/moderation.py` | ✅ inclui ofuscação (leetspeak, base64, letras espaçadas, invisíveis, inglês) |
| Bônus multi-provider (mais de um modelo e mais de um prompt) | `src/chain/multi_provider.py` (matriz em `RunnableParallel`) | ✅ |

---

## 3. Aderência ao conteúdo das aulas

| Aula | O que foi ensinado | Como aparece no projeto |
|---|---|---|
| 01 — LCEL, ChatOllama, parsers | composição com `\|`, `invoke/stream/batch`, `StrOutputParser` | `montar_chain_resposta`; `RunnableBranch`, `RunnablePassthrough.assign` e `RunnableParallel` no pipeline e no multi-provider; `with_fallbacks` para resposta vazia |
| 02 — Memória conversacional | memória por sessão, limite de tokens, política de resumo, `load_memory_variables` | `HistoricoComLimiteDeTokens`; limite justificado em medição (174 tokens/turno da Sprint 2 → 1200 cobre ≈6,9 turnos); política de resumo **estruturada**, documentada; `load_memory_variables()` exposto na demo e na interface |
| 03 — Structured output Pydantic v2 | `PydanticOutputParser`, `format="json"`, `field_validator`, retry | `montar_chain_extracao` + autocorreção de 1 tentativa devolvendo o erro de validação ao modelo |
| 04 — Context engineering | XML tagging, medição com tiktoken, versionamento de prompt | prompt v2 em XML, canário, spotlighting da entrada; `o200k_harmony`; instrução de formato compacta gerada do schema (1.060 → 508 tokens) |

---

## 4. Achados desta auditoria (e o que foi feito)

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| 1 | `src/app.py` quebrava com traceback do httpx quando faltava chave ou o Ollama local estava desligado | média (UX/demonstração) | erro capturado, mensagem acionável apontando `src.teste_auth` |
| 2 | O runner gravava resultado mesmo com todos os casos falhando por rede; esse arquivo poderia virar número de relatório | **alta (integridade de dados)** | aviso explícito no runner + `gerar_relatorios` descarta execução com >20% de casos com erro e registra o descarte |
| 3 | A página de Avaliação da interface quebrava ao abrir resultado do formato antigo (sem o campo `rota`) | média | leitura tolerante com `.get()`; teste de renderização cobre todas as 7 páginas |
| 4 | Métrica de structured output dava acerto para campos `null` quando a extração falhava inteira | **alta (métrica enganosa)** | falha total passa a contar 0 acertos |
| 5 | Falso positivo de escopo em pergunta legítima com termo em inglês ("state of charge") | média | léxico do domínio ampliado; regressão de 44 perguntas legítimas |
| 6 | Régua de pontuação: termo `"h"` casava com qualquer texto e listas contavam como 1 frase | média | `pontuacao.py` v1.1, com todas as colunas reexecutadas na mesma régua |
| 7 | `Runnable` usado em anotação sem import (falha só apareceria em avaliação de tipos) | baixa | import corrigido; `pyflakes` limpo em `src`, `evals` e `tests` |
| 8 | Célula "pendente" indistinguível de "não se aplica" nas tabelas | baixa | colunas sem structured output passam a mostrar `n/a` |

Nenhum achado em aberto. Análise estática limpa; 122 testes passando; `ai/` verificado como
idêntico ao original (`diff -rq` sem saída).

---

## 5. Riscos residuais (declarados, não corrigidos de propósito)

| Risco | Por que fica | Mitigação existente |
|---|---|---|
| Guardrails por regra não cobrem paráfrase criativa infinita | classificador LLM também é vulnerável a injection e não é auditável | defesa em profundidade: prompt v2 (spotlighting + canário) e validador de saída |
| As 44 perguntas legítimas foram escritas junto com as regras | viés de autor inevitável em conjunto próprio | declarado no relatório e em `docs/VALIDACAO.md`; conjunto versionado para terceiros ampliarem |
| 28 casos são amostra pequena | eval maior não cabe no prazo/cota da sprint | pesos por caso, juiz externo e checagem determinística combinados |
| Juiz LLM erra | qualquer avaliação automática de texto erra | juiz fora dos modelos avaliados, temperatura 0, divergências juiz × checador sinalizadas caso a caso |
| Eficiência DC e desaceleração acima de 80% em DC são premissas | não há medição própria nem fonte confiável no escopo | marcadas como premissa no próprio texto do cálculo |
| `ConversationTokenBufferMemory` e `RunnableWithMessageHistory` são deprecated no LangChain 1.x | o escopo da sprint exige essas classes | adaptador isolado em um módulo; migração para LangGraph é trabalho de Módulo 3/4 |
| Reprodutibilidade em servidor compartilhado | `seed` não garante determinismo na nuvem | seed fixa + recomendação de rodar o eval duas vezes e reportar variação |

---

## 6. Condições de entrega (§10)

| Condição | Verificação |
|---|---|
| Repositório público com histórico de commits de cada integrante | `evals/validar_entrega.py` lista os autores encontrados no `git log` |
| Sem API key no histórico | `.env` no `.gitignore`; validador varre arquivos versionados procurando chave |
| Relatório de evolução em PDF na pasta `docs/` | `docs/relatorio_evolucao.pdf` (2 páginas, limite 5) |
| `.txt` com nome, RM e turma | pendente do grupo, junto com `docs/equipe.json` |

Estado atual do checklist automático: rode `python -m evals.validar_entrega`. Os itens que
ainda acusam FALTA dependem de executar o eval com chave de API e de preencher a equipe.

---

## 7. Parecer

O projeto cumpre os seis itens do escopo, os cinco pontos obrigatórios do §6 e o bônus.
A arquitetura respeita a restrição central do experimento: o código da Sprint 2 permanece
intacto como grupo de controle, e cada camada nova (framework, prompt, structured output,
guardrails) é medida separadamente, o que permite atribuir o ganho a quem de direito.

O que falta para a entrega não é código: é executar a bateria com chave de API, preencher a
divisão de trabalho e conferir as respostas à mão, conforme `docs/VALIDACAO.md`.
