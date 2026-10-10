# Fase 6 — Relatórios e entrega · 21 e 22/10

> Cole este arquivo inteiro como primeira mensagem numa sessão de Claude Code aberta na
> raiz do repositório. O `CLAUDE.md` já carrega sozinho.
>
> **O PDF desta fase é condição de entrega, não só item de rubrica.** Sem ele a Sprint 04
> está incompleta mesmo com todo o código funcionando. É o primeiro item da lista de
> "nunca cortar".

## Por que esta fase é mais barata do que parece

Se você escreveu o changelog a cada fase, como o contrato manda, metade do relatório já
está escrita. O `docs/CHANGELOG_SPRINT4.md` tem as decisões, os achados, os comandos e as
saídas — falta organizar, não descobrir.

Se **não** escreveu, reserve o dobro do tempo e comece por reconstruir a história pelo
`git log --oneline` antes de qualquer outra coisa.

## Entregável 1 — `docs/relatorio_rag.md`

Exigido nominalmente pelo §5. É o documento técnico do pipeline:

- Decisões de chunking: `chunk_size`, `chunk_overlap`, `separators`, **com a justificativa
  medida** — o quadro 256 / 512 / 1024 da Fase 5 entra aqui
- Composição da base: quantos documentos por categoria, quantas páginas, quantos chunks
- Parâmetros do retriever: `k`, tipo de busca, limiar de relevância e por que 0,75
- Como o grounding é garantido: as três instruções do `prompt_rag`, a frase de recusa, o
  delimitador anti-injection
- **As divergências das aulas**, com a justificativa: `langchain_chroma` em vez de
  `langchain_community.vectorstores`, `os.getenv` em vez de `userdata.get`,
  `gpt-oss:120b`/`gemma4:31b` em vez de `qwen3.6:27b`. A tabela está pronta na seção 3 do
  `CLAUDE.md` — copie de lá. Declarar isso evita que o avaliador leia como erro.

## Entregável 2 — conferir o que a Fase 5 já produziu

`docs/relatorio_modelos.md` e `prompts/versoes_rag.md` saíram da fase anterior. Releia os
dois procurando **célula vazia ou número não medido**. A regra do grupo é clara: se não
rodou, fica em branco — mas em branco com uma linha explicando por quê, não em branco e
silencioso.

## Entregável 3 — o relatório de evolução (PDF, ≤5 páginas)

A estrutura mínima é a do §8 e **não é negociável**:

**1. Resumo da evolução** — RAG das Sprints 1/2 e o conversacional da Sprint 03 → o RAG
medido e com interface da Sprint 04. Meia página.

**2. Pipeline RAG** — decisões de chunking (tamanho, overlap), base montada, trade-offs.
Resumo do entregável 1, não cópia.

**3. Tabela de comparativo antes/depois — OBRIGATÓRIA.** Colunas "Sprints 1/2 (versão
original)" × "Sprint 04 (RAG avaliado)", com no mínimo:

| Linha | Sprints 1/2 | Sprint 04 |
|---|---|---|
| Score por iteração | nota 1.119 · conformidade 28,6% (`evals/baseline_sprint3/`) | faithfulness e answer_relevancy das 2 iterações |
| Qualidade do contexto recuperado | não havia recuperação — contexto fixo no prompt | top-k do ChromaDB, com score de similaridade |
| Presença de citação de fonte | ausente | documento + página em toda resposta |

A coluna "antes" está **congelada e medida com modelo real** em `evals/baseline_sprint3/`
— são 7 JSONs. Use esses números, não lembranças.

**4. Problemas encontrados e soluções — mínimo 2, com a decisão e o porquê.** Você tem
mais que dois de verdade, todos registrados no changelog. Os mais fortes:

- O guardrail de escopo recusava "lei" e "artigo", e a base passou a ter a Lei SP
  18.403/2026 — o bot recusaria a pergunta que deveria responder. Solução: inverter a
  ordem, o retriever decide primeiro, a regra jurídica vira a rede quando nada passa do
  limiar.
- `ragas 0.4.3` quebra no import com `langchain-community 0.4.2`. Solução: pin em `0.4.1`,
  validado.
- `prompts/base_produtos.json` contradizia o datasheet oficial (7,4 kW × `GW7K-HCA-20`
  7000 W). Solução: a especificação saiu do prompt e passou a vir só da base vetorizada.
- O prompt v2 da Sprint 3 nunca foi medido com modelo real — rodou contra o servidor falso.
  Solução: descartado da linha de base.

**5. Equipe e divisão de trabalho** — nome, RM e tarefa principal de cada um. Seja honesto
sobre quem fez o quê. Um relatório que diz "Davi: todo o código; fulano: base de
conhecimento e relatório" é melhor do que quatro linhas idênticas que o `git shortlog`
desmente.

Gere o PDF a partir de um markdown em `docs/`. O `reportlab` já esteve no projeto
(`git show sprint3-final:evals/relatorio_pdf.py`) — ou exporte do editor, tanto faz. O que
não pode é passar de 5 páginas.

## Entregável 4 — a entrega em si (§10)

- [ ] Repositório **público** e com acesso ao professor
- [ ] `.txt` com **nome, RM e turma** de cada integrante
- [ ] `README.md` da raiz atualizado: a tabela de status ainda diz "a fazer" em quase tudo
- [ ] `app/README.md` com o passo a passo de execução e os prints da Fase 3
- [ ] `git log` com commits de mais de um autor (`git shortlog -sn` para conferir)
- [ ] Nenhuma chave no histórico: `git log --all --oneline -- .env` tem que voltar vazio

## Gate final — 22/10, antes de congelar

Clone o repositório numa pasta nova e siga o próprio `app/README.md`, do zero, como se
você fosse o professor:

```bat
cd %TEMP%
git clone https://github.com/DaviZuolo07/GoodWe_Final_App teste-entrega
cd teste-entrega
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM colar a chave
python -m src.rag.vector_store --reindexar
python app/main.py
```

Se qualquer passo falhar, **é assim que o avaliador vai ver**. É o teste mais valioso da
sprint inteira e quase ninguém faz. Reserve uma hora para ele.

```bat
git add -A
git commit -m "Fase 6: relatorios e relatorio de evolucao"
git push origin develop

git switch main
git merge develop
git push origin main
git switch develop
```

A `main` tem que terminar a sprint com o estado entregue — ela é a branch padrão e é o que
o professor vê ao abrir o repositório.
