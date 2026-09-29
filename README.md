# GoodWe ChargeOps AI Assistant

Chatbot de recarga de veículos elétricos em condomínios, **EV Challenge 2026 ·
FIAP × GoodWe Brasil** · Prompt and Artificial Intelligence · Prof. Jorge Luiz Gomes.

## Integrantes

| Nome | RM |
|---|---|
| Davi Q. Zuolo | 571669 |
| Gustavo Zagato | 569420 |
| Daniel Vilela Mana | 571632 |
| Kayo Henderson | 570706 |

## Sprint 04 — RAG medido, confiável e utilizável (em andamento)

Entrega em 23/10/2026. Andamento por feature em [`docs/CHANGELOG_SPRINT4.md`](docs/CHANGELOG_SPRINT4.md).

| # | Requisito do enunciado | Onde fica | Status |
|---|---|---|---|
| 1 | Base expandida em ChromaDB persistente + `nomic-embed-text` | `data/knowledge_base/`, `src/rag/` | a fazer |
| 2 | Pipeline PyMuPDFLoader → RecursiveCharacterTextSplitter → retriever → prompt RAG versionado | `src/rag/` | a fazer |
| 3 | Grounding + citação de fonte em toda resposta | `src/rag/prompt_rag.py` | a fazer |
| 4 | Avaliação RAGAS (faithfulness, answer_relevancy) ou fallback manual | `evals/` | a fazer |
| 5 | Interface web com citação visível | `app/` | a fazer |
| 6 | Recusa fora do contexto + proteção contra injection via documentos | `src/guardrails/`, `src/rag/` | parcial (guardrails de entrada prontos) |
| 7 | Relatório de evolução (PDF, até 5 págs.) + `relatorio_rag.md` + `relatorio_modelos.md` | `docs/` | a fazer |

## Estrutura

```
data/knowledge_base/   PDFs do domínio (ver README da pasta)
src/chain/             núcleo LCEL: builder, fábrica de LLMs, memória por sessão, prompts, tokens, multi-provider
src/rag/               pipeline RAG (Sprint 04)
src/guardrails/        moderação de entrada (injection/jailbreak) e validação de escopo/saída
src/schemas/           schemas Pydantic v2 (ConsultaRecarga, CalculoRecarga, RespostaTurno)
src/dominio/           calculadora determinística de recarga (o LLM extrai, o Python calcula)
prompts/               system prompts versionados (v1, v2) + base de produtos
evals/                 eval de guardrails + linha de base congelada da Sprint 3
tests/                 testes offline (não chamam modelo)
app/                   interface web (Sprint 04)
docs/                  relatórios
```

## Como rodar

```bash
python -m venv venv && venv\Scripts\activate      # Windows (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                              # cole sua OLLAMA_API_KEY no .env
python -m pytest tests -q                           # testes offline
python -m evals.guardrails_eval                     # eval dos guardrails (offline)
python -m src.teste_auth                            # confere chave, host e modelos do Ollama Cloud
python -m src.app --detalhes                        # conversar pelo terminal
```

## Histórico

O código das Sprints 1, 2 e 3 (inclusive o legado `ai/` e o SQLite) está
preservado na tag Git `sprint3-final`. Os resultados medidos dessas sprints
ficam em `evals/baseline_sprint3/` e são a coluna "antes" do relatório.
