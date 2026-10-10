# Relatório de modelos e parâmetros — Sprint 04 (§6)

Comparação de modelos no pipeline RAG, com os quatro parâmetros pedidos pelo §6
(`temperature`, `k`, `top_p`, `max_tokens`). Números medidos em 10/10/2026; arquivos em
`evals/resultados/`. Perfis de parâmetro em `src/chain/llm.py` (`PERFIS["rag"]`).

## 1. Parâmetros (iguais para todos os modelos comparados)

| Parâmetro | Valor | Onde | Por quê |
|---|---|---|---|
| `temperature` | **0** | `PERFIS["rag"]` | contrato (§6 e invariante 4): resposta só do contexto e medida no RAGAS; greedy decoding minimiza variação |
| `top_p` | **1,0** | `PERFIS["rag"]` | com temperature 0 o top_p não altera a escolha; fixado em 1 para não haver um segundo filtro implícito |
| `max_tokens` (`num_predict`) | **2048** | `PERFIS["rag"]` | no Ollama o `num_predict` inclui os tokens de **raciocínio** do gpt-oss; com 400 tokens (Sprint 3) parte das respostas saía vazia. A concisão é controlada pelo prompt (`<formato>`), não pelo corte |
| `k` (top-k do retriever) | **4** | `src/rag/retriever.py` | recall do retriever 1,000 com chunk 1000/150 e separadores por estrutura; k=8 não acrescenta recall e dobra o contexto (tabela 3) |
| limiar de relevância | 0,65 | `src/rag/retriever.py` | calibrado no corpus (`docs/relatorio_rag.md` §4) |
| `seed` | 42 | `PERFIS["rag"]` | reexecução; na nuvem compartilhada é "melhor esforço" |
| `think` | `low` (só gpt-oss) | `.env` `OLLAMA_THINK` | o gemma4 devolve vazio quando recebe o campo; a fábrica não o envia |

## 2. Modelos comparados no eval RAGAS

Mesma configuração (prompt v1, chunk 1000/150 com separadores por estrutura, k 4), mesmo
eval set de 16 casos, mesmo juiz (`gpt-oss:120b`, temperature 0).

| Modelo | Provedor | Faithfulness | Answer relevancy | Fidelidade manual | Relevância manual | Taxa de resposta | Fonte certa | Recusa correta | Tokens entrada/saída por turno | Arquivo |
|---|---|---|---|---|---|---|---|---|---|---|
| **gpt-oss:120b** (principal) | Ollama Cloud | **0,976** | 0,780 / 0,742 (2 execuções) | 1,00 | 1,00 | 100% | 100% | 2/2 | 1.379 / 82 | `ragas_2a_*`, `ragas_2a-repeticao_*` |
| **gemma4:31b** (comparação) | Ollama Cloud | 0,964 | 0,743 | 1,00 | 1,00 | 100% | 100% | 2/2 | 1.441 / 70 | `ragas_modeloB-gemma4_20261010_003837.json` |

**Leitura.** Os dois modelos empatam dentro do ruído medido (answer_relevancy varia 0,04
entre execuções idênticas). A única diferença de faithfulness é M05: o gemma4 escreveu
"9600" sem a unidade, e o juiz extraiu uma afirmação que não casou com o trecho (0,5). Com
o retriever trazendo o trecho certo, um modelo de 31B segura o grounding tão bem quanto o
de 120B — o gargalo da iteração 1 era a recuperação, não o tamanho do modelo. O
gpt-oss:120b fica como principal por ser o modelo da linha de base da Sprint 3 (mesma
régua do antes/depois).

## 3. Efeito de `k` e de `chunk_size` (recall do retriever, sem LLM)

`python -m evals.recall_retriever` — fração dos 14 casos respondíveis em que a evidência
literal da resposta chegou aos trechos acima do limiar.

| Separadores | chunk 256, k 4 | 512, k 4 | 1000, k 4 | 512, k 8 | 1000, k 8 |
|---|---|---|---|---|---|
| aula | 0,643 | 0,857 | 0,857 | 0,929 | 0,929 |
| estrutura | 0,643 | 0,929 | **1,000** | 1,000 | 1,000 |

Subir k de 4 para 8 recuperou um caso a mais com os separadores da aula, ao custo de
dobrar o contexto; trocar os separadores recuperou os dois sem custo. Detalhe e quadro do
RAGAS por chunk_size em `docs/relatorio_rag.md` §2.

## 4. Multi-provider (bônus) — modelo × prompt num único `RunnableParallel`

```
python -m src.chain.multi_provider "Qual o grau de proteção IP do carregador HCA G2 e do plugue?" \
       --rag --modelos gpt-oss:120b,gemma4:31b,local:qwen3.5:4b --prompts v1,v2
```

Seis ramos em paralelo, **dois provedores** (Ollama Cloud e Ollama local, endpoints e
credenciais diferentes) × **dois prompts RAG**. Mesmo retriever em todos os ramos.
Arquivo `evals/resultados/multi_provider_rag_20261010_002659.json`.

| Modelo | Provedor | Prompt | Latência | Tokens entrada / saída | Resultado |
|---|---|---|---|---|---|
| gpt-oss:120b | nuvem | rag_v1 | 5,8 s | 1.643 / 88 | IP66 e IP55, citando o FAQ pág. 2 |
| gpt-oss:120b | nuvem | rag_v2 | 6,3 s | 1.774 / 84 | idem |
| gemma4:31b | nuvem | rag_v1 | 7,0 s | 1.687 / 44 | idem |
| gemma4:31b | nuvem | rag_v2 | 7,8 s | 1.819 / 85 | idem, mais uma frase com a mesma citação |
| qwen3.5:4b | **local** | rag_v1 | 287,7 s | 3.312 / 4.223 | resposta correta e citada, depois de 4.223 tokens de raciocínio |
| qwen3.5:4b | **local** | rag_v2 | 256,5 s | — | resposta vazia (orçamento consumido no raciocínio) |

O modelo local de 4B, na GPU desta máquina, é inviável para a interface (4–5 minutos por
resposta) e falha por orçamento de tokens num dos prompts. Confirma a escolha dos modelos
de nuvem como principal e comparação.

**Sobre latência.** No eval RAGAS a latência média por turno foi ~0,7 s para os dois
modelos, valor que provavelmente reflete cache de prompt da Ollama Cloud (os mesmos 16
prompts se repetem entre execuções, com seed fixa). A latência realista de uma pergunta
nova é a do multi-provider: 5,8–7,8 s nos modelos de nuvem.

## 5. Modelo não medido

| Modelo | Situação |
|---|---|
| `kimi-k2.6` (escolha do grupo para a entrega) | A Ollama Cloud respondeu, em 10/10/2026, *"this model is not included in your free usage, add usage credits"*, tanto direto (`kimi-k2.6`) quanto pelo Ollama local (`kimi-k2.6:cloud`). Sem número. O código aceita os dois nomes (`src/chain/llm.py` remove o sufixo `:cloud` ao falar direto com a nuvem). Com créditos: `OLLAMA_MODEL=kimi-k2.6` no `.env` e reexecutar `python -m evals.ragas_eval --iteracao 1 --prompt v1 --separadores aula` e `--iteracao 2 --prompt v1`. |
