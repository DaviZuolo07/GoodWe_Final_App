# Ambiente técnico — Sprint 03

Gerado automaticamente por `src/diagnostico.py` em 20/09/2026 22:44.

## Plataforma

- Python 3.12.3
- Linux 6.18.44-fc-v37

## Versões fixadas

| Pacote | Versão |
|---|---|
| `langchain` | 1.3.18 |
| `langchain-core` | 1.6.1 |
| `langchain-ollama` | 1.1.0 |
| `langchain-classic` | 1.0.8 |
| `langgraph` | 1.2.11 |
| `pydantic` | 2.13.5 |
| `tiktoken` | 0.14.0 |

## Modelo

| Item | Valor |
|---|---|
| Host | `` |
| Modo | local |
| Modelo principal | `` |
| Modelo de comparação | `a definir` |
| Reasoning (`think`) | `low` |

## Perfis de parâmetros

Definidos em `src/chain/llm.py`. Cada perfil é uma decisão registrada.

| Perfil | temperature | top_p | max_tokens (num_predict) | seed |
|---|---|---|---|---|
| `classificador` | 0.0 | 1.0 | 512 | 42 |
| `redator` | 0.2 | 0.9 | 1024 | 42 |
| `estruturado` | 0.0 | 1.0 | 1024 | 42 |
