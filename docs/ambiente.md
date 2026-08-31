# Ambiente técnico — Sprint 03

Gerado automaticamente por `src/diagnostico.py` em 31/08/2026 19:42.

## Plataforma

- Python 3.14.7
- Windows 11

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
| Host | `https://ollama.com` |
| Modo | Ollama Cloud |
| Modelo principal | `gpt-oss:120b` |
| Modelo de comparação | `qwen3:8b` |
| Reasoning (`think`) | `low` |

## Perfis de parâmetros

Definidos em `src/chain/llm.py`. Cada perfil é uma decisão registrada.

| Perfil | temperature | top_p | max_tokens | Uso |
|---|---|---|---|---|
| `classificador` | 0.0 | 1.0 | 160 | roteamento de intenção (reprodutível) |
| `redator` | 0.2 | 0.9 | 400 | resposta ao usuário |
| `estruturado` | 0.0 | 1.0 | 500 | saída Pydantic (JSON válido de primeira) |
