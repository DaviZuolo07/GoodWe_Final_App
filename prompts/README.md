# Prompts versionados

Cada versão é um arquivo `system_prompt_vN.md` com cabeçalho (`versao`, `data`,
template da mensagem humana). O builder carrega por argumento
(`ChatbotChargeOps(versao_prompt="v2")`). O cabeçalho entre `---` é removido
pelo carregador antes de ir ao modelo.

`base_produtos.json` é hoje a única fonte de especificação de produto. Na
Sprint 04 ela será substituída pela base de conhecimento em `data/knowledge_base/`
recuperada via ChromaDB. O **prompt RAG** versionado exigido pela Sprint 04 fica
em `src/rag/prompt_rag.py` e terá tabela própria.

## Histórico do system prompt (Sprint 3) — só números medidos

Mesmo eval set de 28 casos, modelo `gpt-oss:120b`. Arquivos-fonte em
`evals/baseline_sprint3/`.

| Versão | O que mudou | Nota do juiz (0–2) | Conformidade | Tokens/turno |
|---|---|---|---|---|
| legado (Sprints 1/2) | system_prompt.txt + contexto GoodWe + 11 few-shots em toda chamada | 1,119 e 1,275 (2 execuções) | 28,6% e 39,3% | ~5.000 |
| sem prompt (LCEL cru) | chain LCEL com system genérico, para isolar o efeito do framework | 1,000 | 35,7% | 915 |
| v1 | identidade, escopo, recusas com encaminhamento a profissional, limite de formato | 1,707 e 1,714 (2 execuções) | 67,9% e 75,0% | ~1.375 |
| v2 | XML tagging, spotlighting em `<pergunta_usuario>`, canário, `<calculo_verificado>`, `<fatos_da_sessao>` | **não medido** | **não medido** | — |

O v2 é o prompt em uso, mas **nunca foi medido com modelo real**: a única
execução registrada (20/09) rodou contra o servidor falso de testes e foi
descartada. Achado: o framework sozinho não melhorou a nota (legado → LCEL cru);
o ganho veio do prompt versionado (LCEL cru → v1).
