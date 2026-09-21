# Prompts versionados

Cada versão é um arquivo `system_prompt_vN.md` com cabeçalho (versão, data, template da mensagem humana). O builder carrega por argumento (`ChatbotChargeOps(versao_prompt="v2")`) e o runner mede cada versão com o mesmo eval. Tabela gerada por `evals/gerar_relatorios.py`.

| Versão | Data | O que mudou | Por quê | Tokens do system | Nota juiz | Conformidade | Latência média | Tokens/turno |
|---|---|---|---|---|---|---|---|---|
| v0 (legado) | Sprint 2 | system_prompt.txt + GOODWE_CONTEXT + 11 few-shots, enviados em toda chamada | ponto de partida | 3700 | pendente | pendente | pendente | pendente |
| v1 | 2026-09-01 | prompt consolidado em markdown: escopo, recusas com encaminhamento, limite de 4 frases, sem LaTeX/tabelas | respostas prolixas (12–15 frases no LCEL cru) e recusas sem encaminhamento | 307 | pendente | pendente | pendente | pendente |
| v2 | 2026-09-15 | XML tagging por seção; spotlighting da entrada em <pergunta_usuario>; canário anti-vazamento; <base_produtos>; <calculo_verificado> e <fatos_da_sessao> preenchidos pelo código; 3 few-shots curtos | isolar instrução de dado (injection), tirar a aritmética do modelo, fatos sobreviverem à janela de memória | 987 | pendente | pendente | pendente | pendente |

Régua de tokens: `o200k_harmony`. "Tokens do system" = texto fixo do system prompt com os blocos dinâmicos vazios. O v2 é maior que o v1 porque carrega a base de produtos, os exemplos e as seções de segurança; o ganho de custo em relação ao legado vem de enviar ~1/4 dos tokens fixos.

`base_produtos.json`: única fonte de especificação de produto. O que não está nele é recusado (§6: não inventar especificação de produto fora da base).
