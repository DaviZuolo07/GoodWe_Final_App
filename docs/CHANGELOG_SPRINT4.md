# Changelog — Sprint 04

## F0 — Faxina, segurança e fundação (29/09/2026)

Aprovada pelo Daniel com as decisões D1–D4: apagar `ai/` após a tag, apagar o
SQLite, interface em Gradio, manter só a linha de base medida.

### Preservação
- Tag Git `sprint3-final` no commit `bc3e78f`: todo o código das Sprints 1–3
  (legado `ai/`, SQLite, runner, juiz, relatórios) continua recuperável.
- Resultados medidos com modelo real movidos para `evals/baseline_sprint3/`
  (coluna "antes" do relatório).

### Removido (código morto, legado e arquivos antigos)
- `ai/` (chatbot legado) e `database/` (SQLite usado só pelo legado).
- Pastas vazias: `backend/`, `frontend/`, `datasets/`, `scripts/`, `docs/modbus/`,
  `docs/meetings/`, `src/graph/`.
- `src/chain/hello_lcel.py` (exemplo, marcado como "não vai para a entrega"),
  `src/chain/execucao.py` (não era importado), `src/diagnostico.py` (sobreposto
  ao `teste_auth.py`).
- Eval da Sprint 3 acoplado ao legado: `adaptadores.py`, `runner.py`, `juiz.py`,
  `executar_tudo.py`, `gerar_relatorios.py`, `relatorio_pdf.py`,
  `validar_entrega.py`, `structured_eval.py`, `structured_set.json`,
  `memoria_demo.py`, `sprint3_results.json` (estava todo com valores nulos).
- `tests/servidor_ollama_falso.py` (nenhum teste usava).
- `src/schemas/resultados.py`: classe `VereditoJuiz` (só o juiz apagado usava).
- `src/chain/prompts.py`: função `tokens_legado()` (lia arquivos do `ai/`).
- Docs das Sprints 2/3: `docs/agents/`, `docs/architecture/`, `docs/database/`,
  relatório e tabela da Sprint 3 (saíram com células "pendente"), `COMO_TESTAR`,
  `VALIDACAO`, `RELATORIO_MUDANCAS`, `ambiente.md`, `equipe.json`,
  `test_cases.md`, `modelos_disponiveis.json`, `relatorio_modelos.md` (refeito na F5).
- `requirements-sprint3.txt` e `prompts/versoes.md` (tabela duplicada e
  conflitante com `prompts/README.md`).
- 24 JSONs de execuções de teste em `evals/resultados/` (a maioria contra o servidor falso).

### Corrigido
- `requirements.txt` era inválido (`openai - gpt-oss:120b` não é sintaxe de pip).
  Agora é um arquivo único com versões fixadas e testadas juntas, incluindo a
  stack da Sprint 04 (chromadb, pymupdf, langchain-chroma,
  langchain-text-splitters, ragas, datasets, gradio).
- Incompatibilidade descoberta: `ragas 0.4.3` quebra no import com
  `langchain-community 0.4.2`. Fixado `langchain-community==0.4.1`, validado.
- `src/teste_auth.py` executava chamadas de rede ao ser importado. Execução
  movida para `main()` com guarda `if __name__ == "__main__"`, sem mudar a lógica.
- `.env.example`: removida `MODELO_JUIZ` (juiz apagado).
- `.gitignore`: adicionados `chroma_db/`, `.pytest_cache/`, `.gradio/` e
  `docs/modelos_disponiveis.json` (gerado pelo `teste_auth`).
- Docstrings que citavam arquivos apagados foram ajustadas.

### Criado
- `data/knowledge_base/README.md`: o que coletar, regras e registro de origem (F1).
- `src/rag/__init__.py` e `app/` (vazios, recebem código na F2 e F6).
- `evals/baseline_sprint3/README.md` e `prompts/README.md` unificado, só com
  números medidos.
- `README.md` raiz reescrito para o estado atual (o anterior documentava o legado).

### Achados registrados
- O prompt v2 (em uso) **nunca foi medido com modelo real**: a execução de 20/09
  rodou contra o servidor falso de testes. Arquivo descartado da linha de base.
- A chave do Ollama estava no `.env` dentro do zip enviado para a auditoria. Ela
  nunca foi commitada (histórico conferido), mas deve ser trocada.

### Verificação
- `pytest tests`: 111 passaram.
- `python -m evals.guardrails_eval`: 39/39 ataques bloqueados, 0 falsos positivos
  (igual à Sprint 3).
- 28 módulos de `src/`, `evals/` e `tests/` importam sem erro.
- Imports dos slides das Aulas 05–08 (PyMuPDFLoader, RecursiveCharacterTextSplitter,
  OllamaEmbeddings, Chroma, ragas, Dataset, gradio) validados; persistência do
  Chroma testada offline.
