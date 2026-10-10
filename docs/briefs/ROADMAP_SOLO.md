# Roadmap Sprint 04 — execução solo

14 dias, uma pessoa, zero paralelismo. Este arquivo manda; os briefs em `docs/briefs/`
são o detalhe técnico de cada fase.

---

## Como trabalhar

**Uma sessão de Claude Code por fase**, aberta na raiz do repositório. O `CLAUDE.md`
carrega sozinho e leva contrato, stack e invariantes. Cole o brief da fase como primeira
mensagem.

Não emende fases na mesma sessão. O contexto fica grande, a sessão começa a esquecer os
invariantes e você perde o controle do que foi verificado. O **changelog é o handoff**:
cada fase fecha escrevendo nele, e a sessão seguinte lê de lá onde o trabalho parou.

**Commit ao fim de cada fase**, na `develop`, com a saída do comando de verificação colada
no changelog. Sem isso você não tem como voltar quando algo quebrar — e você vai precisar.

---

## O cronograma

| Dias | Fase | Brief | O que existe no fim |
|---|---|---|---|
| 09/10 | **Passo 0** | `PASSO_0.md` | git limpo, chave nova, `nomic-embed-text` confirmado |
| 10–13/10 | **1 · Pipeline RAG** | `FASE_1_pipeline_rag.md` | pergunta entra, resposta sai com documento e página |
| 14–15/10 | **2 · Base + eval set** | `FASE_2_base_conhecimento.md` | 4 categorias indexadas, 8–10 casos de avaliação |
| 16–17/10 | **3 · Interface** | `FASE_3_interface.md` | Gradio no ar com painel de fontes |
| 18–19/10 | **4 · RAGAS iteração 1** | `FASE_4e5_avaliacao.md` | primeiro número de faithfulness |
| 20–21/10 | **5 · Prompt v2 + iteração 2** | `FASE_4e5_avaliacao.md` | ganho medido entre as duas |
| 21–22/10 | **6 · Relatórios** | `FASE_6_relatorios.md` | 3 markdowns + PDF de 5 páginas |
| 22/10 | Congelamento | — | nada entra depois disto |
| 23/10 | **ENTREGA** | — | repo + interface + PDF + `.txt` da equipe |

A sobreposição em 21/10 é proposital: o eval roda sozinho por vários minutos e esse tempo
de parede é quando se escreve relatório.

---

## A inversão em relação ao plano de 4 pessoas

**O pipeline vem antes da base de conhecimento.** No plano anterior a base vinha primeiro
porque outra pessoa escrevia os PDFs em paralelo. Sozinho, isso vira espera pura.

Então: a Fase 1 nasce contra os **3 PDFs GoodWe que já estão em `data/knowledge_base/`**.
São 76 páginas de conteúdo real — mais que suficiente para construir e testar o pipeline
inteiro. A base expandida entra na Fase 2 com um `--reindexar`. **O código não muda; só o
conteúdo da coleção.**

---

## O que delegar (e por quê isso não é opcional)

Você disse que faz todas as *features*. Estes quatro itens não são features — são conteúdo
e redação, somam uns 4 dias, e saem direto do orçamento das iterações de RAG:

| Item | Quem pode fazer | Quando precisa estar pronto |
|---|---|---|
| Os 3 PDFs: regimento, FAQ, tarifa | qualquer um do grupo | 14/10 |
| As 8–10 perguntas do `eval_set_rag.json` | quem conhece o domínio | 15/10 |
| Relatório de evolução (PDF, ≤5 págs.) | qualquer um | 22/10 |
| `.txt` com nome, RM e turma de cada um | qualquer um | 23/10 |

Há um segundo motivo, de rubrica: o §10 exige "commits regulares **de cada integrante**".
Hoje os 11 commits são todos seus. Se virarem 60 e continuarem todos seus, a condição de
entrega segue descumprida no dia 23 — e isso não se conserta na véspera. Estes quatro
itens são justamente os que geram **commit real de outra pessoa** sem ninguém precisar
entender o pipeline.

Cada um roda isto uma vez, na própria máquina:

```bat
git config --global user.name "Nome Sobrenome"
git config --global user.email "email-do-github@exemplo.com"
```

Confira ao longo da semana com `git shortlog -sn`.

**Se ninguém mais commitar**, o plano continua de pé — mas some a folga, e o corte de
escopo abaixo passa a ser obrigatório em vez de preventivo.

---

## Corte de escopo — decidido agora, não na véspera

Se atrasar, corte **nesta ordem**, de cima para baixo:

1. Normas de prioridade 2 e 3 (Lei SP, IT-41, ANEEL, SolarGo) — a base fecha as 4
   categorias sem elas
2. Reranking, SemanticChunker, LangGraph — já estão fora e continuam fora (§3: NÃO
   OBRIGATÓRIOS, valem 0 ponto)
3. Memória de conversa na interface (`RunnableWithMessageHistory`) — a rubrica pede
   citação visível, não memória
4. Streaming (`yield`) — é experiência, não ponto
5. Bônus multi-provider — vale +1 e o código já existe, mas é o primeiro ponto dispensável

**Nunca corte:** a segunda iteração de RAGAS (bloco D inteiro), a citação de fonte
(bloco B), a recusa fora do contexto (bloco B), o relatório de evolução em PDF (condição
de entrega, não só rubrica).

---

## Gates — não avance sem

| Fim da fase | Tem que ser verdade |
|---|---|
| 1 | uma pergunta respondível traz documento e página; uma fora da base traz a recusa literal |
| 2 | as 4 categorias indexadas; `eval_set_rag.json` com ≥8 casos, incluindo 2 de recusa |
| 3 | `python app/main.py` sobe e o painel de fontes mostra documento, página e score |
| 4 | existe um JSON com faithfulness e answer_relevancy e **todos os parâmetros** juntos |
| 5 | iteração 2 no **mesmo** eval set, com ganho e uma hipótese que o explique |
| 6 | PDF de ≤5 págs. com a tabela antes/depois preenchida com números medidos |

Em todas: `python -m pytest tests -q` passando e `python -m evals.guardrails_eval` em
39/39 com 0 falso positivo.

---

## Disciplina diária (5 minutos, não pule)

No fim de cada dia de trabalho:

```bat
python -m pytest tests -q
git add -A
git commit -m "<fase>: <o que mudou>"
git pull --rebase origin develop
git push origin develop
```

E uma linha no `docs/CHANGELOG_SPRINT4.md`: o que mudou, o que ficou em aberto, e qualquer
achado novo. O changelog do grupo já é a melhor prática do projeto — ele é o que vai
alimentar o relatório de evolução na Fase 6, e escrevê-lo no dia custa 2 minutos contra
2 horas de arqueologia no dia 22.

---

## Os dois riscos que podem custar a sprint

**O Ollama Cloud cair na véspera.** As duas iterações dependem dele. Por isso a iteração 1
é 18/10 e não 21/10 — há margem para repetir. `local:qwen3:8b` é o plano B, já previsto no
`.env.example`.

**O RAGAS quebrar.** Decida **até 16/10** entre RAGAS e rubrica manual. O §4 aceita as duas
sem penalidade, desde que a manual seja documentada e aplicada no mesmo eval set. O brief
da Fase 4 manda escrever o fallback mesmo que o RAGAS funcione — é barato e salva o bloco D.

E lembre que o **CKP03 é dia 26/10**, individual, três dias depois. Congelar em 22/10 não
é conservadorismo, é o que deixa a semana final respirável.
