# GoodWe ChargeOps — Sprint 04 (RAG medido, confiável e utilizável)

Contexto para qualquer sessão de Claude Code neste repositório. **Leia antes de escrever
código.** O que está aqui vem do enunciado oficial do Prof. Jorge Luiz Gomes e das Aulas
05–08; onde é escolha do grupo, está marcado.

---

## 1. O que é o projeto

Chatbot de recarga de veículos elétricos em condomínios. EV Challenge 2026 · FIAP ×
GoodWe Brasil. Entrega da Sprint 04: **23/10/2026**.

Evolução das Sprints 1/2 (chatbot manual, legado) → Sprint 03 (refactory conversacional
em LCEL) → **Sprint 04 (RAG medido, com interface)**.

| Integrante | RM |
|---|---|
| Davi Q. Zuolo | 571669 |
| Gustavo Zagato | 569420 |
| Daniel Vilela Mana | 571632 |
| Kayo Henderson | 570706 |

**Execução:** o Davi faz todo o código, sozinho e em sequência. O plano dia a dia, os
gates de cada fase e a ordem de corte de escopo estão em **`docs/briefs/ROADMAP_SOLO.md`** — leia
antes de propor trabalho novo. Conteúdo e relatórios ficam com o resto do grupo.

---

## 2. Invariantes — nunca quebrar

Isto é contrato com o enunciado. Uma mudança que viole qualquer item abaixo está errada,
mesmo que o código funcione.

1. **Grounding.** O bot responde **somente** com o contexto recuperado. Sem chunk
   relevante, a resposta é exatamente:
   `"Não encontrei essa informação nos documentos fornecidos."`
2. **Citação de fonte em toda resposta.** Formato: `(fonte: <documento>, página X)`.
   O `page` do PyMuPDF é **0-indexado** — exiba sempre `page + 1`.
3. **Nunca inventar especificação de produto.** Se não está na base vetorizada, não
   existe. Vale para potência, modelo, tarifa, prazo, norma.
4. **`temperature=0`** em tudo que for RAG e em tudo que for medido (§6 do enunciado).
5. **Nenhum número sem medição.** Relatório não recebe valor estimado, esperado ou
   lembrado. Não rodou → fica em branco.
6. **Mesma régua nas duas iterações.** Mesmo eval set, mesma `seed`, mesmo tokenizador,
   mesmo `temperature`. Mudou a régua → a comparação morre e as duas pontas reexecutam.
7. **`.env` nunca é commitado nem zipado.** Já vazou duas vezes. `git check-ignore -v .env`
   tem que imprimir a linha do `.gitignore`.
8. **Só `main` e `develop`.** Commit direto na `develop`, pequeno e frequente, com
   `git pull --rebase origin develop` antes do push. Nunca `push --force`, nunca
   `reset --hard` em branch compartilhada.
9. **Cada integrante commita com o próprio nome.** O §10 exige commits regulares de cada
   um. Não commite "em nome de" ninguém.

### O que NÃO fazer sem pedir

- **Não implemente reranking, LangGraph, SemanticChunker, ParentDocumentRetriever ou
  observabilidade antes dos obrigatórios estarem verdes e medidos.** O §3 marca todos
  como NÃO OBRIGATÓRIOS. Valem 0 ponto de rubrica.
- **Não avance para a fase seguinte sem passar o gate da fase atual.** Os gates estão no
  brief de cada fase e no `docs/briefs/ROADMAP_SOLO.md`. Trabalhando sozinho não há quem revise — o
  gate é a revisão.
- **Não faça trabalho de outra fase porque "já que estamos aqui".** O cronograma não tem
  folga e cada fase cabe numa sessão. Achou algo fora do escopo da fase? Registre na seção
  "Achados" do changelog e siga.
- Não apague nem reescreva `evals/baseline_sprint3/`. É a coluna "antes" do relatório,
  congelada e medida com modelo real.
- Não altere `src/guardrails/` sem ler a seção 6 deste arquivo.
- Não troque os modelos configurados no `.env` por outros. (10/10/2026: o grupo escolheu
  `kimi-k2.6`, mas a conta Ollama Cloud responde "not included in your free usage"; as
  medições usam `gpt-oss:120b` + `gemma4:31b`. Com créditos, troque `OLLAMA_MODEL` e
  reexecute as DUAS iterações.)

---

## 3. Stack — versões e imports exatos

Tudo já está fixado em `requirements.txt` e testado junto. **Não suba versão.** Em
particular: `ragas 0.4.3` quebra no import com `langchain-community 0.4.2` — por isso o
pin é `0.4.1`.

```python
# Carga de PDF (Aula 06)
from langchain_community.document_loaders import PyMuPDFLoader

# Chunking (Aula 06)
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Embeddings (Aula 05)
from langchain_ollama import OllamaEmbeddings   # nomic-embed-text, 768 dims

# Vector store — ATENÇÃO, divergência deliberada das aulas
from langchain_chroma import Chroma             # NÃO langchain_community.vectorstores

# Chain (Aula 06)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# Avaliação (Aula 07)
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from datasets import Dataset

# Interface (Aula 08)
import gradio as gr
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
```

### Divergências das aulas — deliberadas, e precisam ir para `docs/relatorio_rag.md`

| Aula usa | Aqui usamos | Por quê |
|---|---|---|
| `langchain_community.vectorstores.Chroma` | `langchain_chroma.Chroma` | o pacote dedicado é o pin do projeto; API idêntica (`from_documents`, `as_retriever`, `similarity_search_with_score`) |
| `google.colab.userdata.get(...)` | `os.getenv(...)` via `python-dotenv` | projeto é local, não notebook (§1 do enunciado) |
| `qwen3.6:27b` | `gpt-oss:120b` + `gemma4:31b` | já medidos na linha de base da Sprint 3; são os 2+ modelos do bloco C |
| `persist_directory="/content/..."` | `chroma_db/` na raiz | gitignored, regenerável |

---

## 4. Estrutura e onde cada coisa mora

```
data/knowledge_base/   PDFs do domínio — ver README da pasta (padrão de nome obrigatório)
src/rag/               pipeline RAG da Sprint 04  ← a construir
src/chain/             núcleo LCEL da Sprint 3: builder, llm, memoria, prompts, tokens, multi_provider
src/guardrails/        moderação de entrada + validação de escopo
src/schemas/           Pydantic v2
src/dominio/           calculadora determinística de recarga
prompts/               system prompts versionados (v1, v2)
evals/                 eval set, guardrails, linha de base congelada  ← RAGAS a construir
app/                   interface Gradio  ← a construir
docs/                  changelog + relatórios
tests/                 testes offline (não chamam modelo)
```

`src/rag/` recebe exatamente os módulos do §5 do enunciado: `loader.py`, `chunking.py`,
`embeddings.py`, `vector_store.py`, `retriever.py`, `prompt_rag.py`.

---

## 5. Convenções do código

O codebase é em **português** e já tem um estilo firme. Siga-o:

- Nomes de módulo, função e variável em português (`montar_chain`, `formatar_contexto`,
  `pontuacao.py`, `memoria.py`).
- `from __future__ import annotations` no topo. Type hints em assinaturas públicas.
- **Docstring de módulo explicando o PORQUÊ**, não o quê. Olhe `src/chain/llm.py` como
  referência: ele documenta a armadilha do `num_predict` com modelos de raciocínio. Essa
  é a régua.
- Parâmetros de modelo vivem em dicionários de perfil (padrão `PERFIS` em `llm.py`), não
  espalhados em chamadas.
- Nada de `print` em módulo de biblioteca; `print` só em `__main__` e em scripts de eval.
- Um módulo não executa rede ao ser importado. Execução vai para `main()` sob
  `if __name__ == "__main__":`.

---

## 6. Guardrails — o conflito que precisa ser resolvido

`src/guardrails/scope_validator.py` hoje **recusa** qualquer pergunta que case com
`lei \d`, `lei n`, `codigo civil`, `artigo \d`, `advogad\w*` e devolve o encaminhamento
jurídico. Isso vale pontos do bloco B ("recusa fora do contexto") e passa 39/39 no eval
de ataques, com 0 falso positivo.

**O problema:** a base de conhecimento vai receber a Lei SP 18.403/2026 e a IT-41. Com a
regra atual, o bot recusa exatamente a pergunta que deveria responder com citação.

**A solução acordada — o retriever decide primeiro:**

1. Roda a moderação de injection/jailbreak (`moderation.py`) — isso continua primeiro.
2. Roda o retriever. Há chunk acima do limiar de similaridade? → responde com citação.
3. Não há? → aí sim cai no `scope_validator`, que decide entre "não encontrei nos
   documentos" e o encaminhamento jurídico/profissional habilitado.

Não apague a regra jurídica. Ela é a rede de segurança para quando o RAG não tem a
resposta. Mude a **ordem**, e registre a mudança no changelog com o eval de guardrails
reexecutado (`python -m evals.guardrails_eval` tem que continuar em 39/39, 0 falso
positivo).

---

## 7. Comandos

```bash
python -m pytest tests -q              # testes offline, não chamam modelo
python -m evals.guardrails_eval        # 39/39 ataques, 0 falso positivo
python -m src.teste_auth               # confere chave, host e modelos do Ollama Cloud
python -m src.app --detalhes           # conversar pelo terminal
```

RAG (Fase 1 — exige o Ollama local com `ollama pull nomic-embed-text`):

```bash
python -m src.rag.vector_store --reindexar    # indexa data/knowledge_base/ no ChromaDB
python -m src.chain.rag "pergunta"            # uma pergunta, com fontes, scores e rota
python -m src.chain.rag --detalhes            # modo conversa
```

Avaliação e interface (Sprint 04, Python 3.13 — o `ragas` não instala no 3.14):

```bash
python -m evals.ragas_eval --iteracao 1 --separadores aula --modo denso --k 4   # iteração 1 (linha de base)
python -m evals.ragas_eval --iteracao 2 --modo denso --k 4                      # iteração 2
python -m evals.ragas_eval --iteracao 3                      # iteração 3 (config padrão: híbrida, k 6)
python -m evals.robustez_eval --modo denso --k 4             # perguntas curtas de morador, ponta a ponta
python -m evals.recall_retriever              # recall do retriever por chunk_size x k x busca, sem LLM
python -m src.chain.multi_provider "pergunta" --rag --modelos gpt-oss:120b,gemma4:31b,local:qwen3.5:4b
python app/main.py                            # sobe a interface Gradio
python -m src.ferramentas.md_para_pdf relatorio   # docs/relatorio_evolucao.md -> PDF (≤5 págs.)
```

---

## 8. Definition of done — toda fase

Uma fase não fecha sem os quatro:

1. Entrada em `docs/CHANGELOG_SPRINT4.md` com: o que mudou, o que ficou em aberto,
   achados que viram tarefa.
2. `python -m pytest tests -q` passando.
3. O comando de verificação da própria fase rodado, com a **saída colada** no changelog.
4. Commit na `develop`, com o nome do autor real.

---

## 9. Rubrica — onde cada bloco é ganho

| Bloco | Pts | O que o avaliador procura |
|---|---|---|
| A | 35 | pipeline end-to-end · vector store persistente · base expandida · interface com citação visível |
| B | 30 | responde só com contexto · cita fonte · recusa fora do contexto · anti-injection via documento · prompt RAG versionado com ganho |
| C | 25 | 2+ modelos comparados com `temperature`, `k`, `top_p`, `max_tokens` · RAGAS ou fallback por iteração |
| D | 10 | ≥2 iterações com ganho medido · relatório de evolução ≤5 págs. com tabela antes/depois |
| Bônus | +1 | multi-provider: >1 modelo e >1 prompt (`src/chain/multi_provider.py` já faz) |

**Prompt injection via documento** (bloco B) é diferente de injection de entrada, que o
`moderation.py` já cobre. É um PDF da base contendo algo como "ignore as instruções
anteriores". A defesa: delimitar o contexto recuperado com marcador explícito no
`prompt_rag.py` e instruir que o conteúdo entre os marcadores é **dado, nunca instrução**.
Coloque um caso desses no `evals/guardrails_set.json`.
