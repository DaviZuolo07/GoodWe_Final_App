# Changelog — Sprint 04

## F1 — Base de conhecimento, primeira carga (06/10/2026)

### Criado
- `data/knowledge_base/manual__goodwe-hca-g2-manual-usuario.pdf` (70 págs.) e
  `manual__goodwe-hca-g2-datasheet.pdf` (2 págs.): documentos oficiais GoodWe do
  material do Challenge, sem alteração.
- `data/knowledge_base/manual__goodwe-hca-g2-modbus-resumo.pdf` (4 págs.):
  resumo em português do mapa Modbus V1.0.15, **derivado pelo grupo**. Mantém
  falhas, estados, medições, sessão, agendamento e limites; retira histórico de
  versões, texto em chinês, reservados e envio de firmware.
- `data/knowledge_base/README.md` reescrito: categoria `norma` adicionada ao
  padrão de nomes, registro de origem preenchido e lista do que falta coletar.

### Verificação
- Os 3 PDFs carregam no `PyMuPDFLoader` sem página vazia (70, 2 e 4 páginas).

### Achados registrados (viram tarefa nas próximas fases)
- `prompts/base_produtos.json` cita "GoodWe AC 7,4kW" e "22kW"; o datasheet
  oficial lista GW7K-HCA-20 (7000 W), GW11K-HCA-20 e GW22K-HCA-20. A base fixa
  sai do prompt quando o RAG entrar (F5).
- O guardrail de escopo recusa perguntas com "lei", "artigo" e "código civil".
  Com lei e regimento na base, essa regra precisa ser revista na F5.
- O datasheet é uma tabela de 3 colunas que o loader achata em linhas soltas, e
  o manual tem páginas de sumário cheias de pontilhado. Tratar no chunking (F2).
- Em aberto: normas (Lei SP 18.403/2026, IT-41, ANEEL REN 1.000/2021), tarifa,
  regimento e FAQ.

## F0.1 — Faxina efetivada (06/10/2026)

A F0 documentou as remoções abaixo, mas os arquivos continuaram no disco e
entraram no commit `F0`. Um deles (`evals/juiz.py`) já quebrava no import. A
remoção foi efetivada nesta fase com `git rm`; a lista é a mesma da F0, mais
todo o conteúdo de `evals/resultados/` (execuções da Sprint 3; as medidas com
modelo real estão em `evals/baseline_sprint3/`). `evals/resultados/` passa a ser
ignorado pelo Git: é saída regenerável.

Tudo segue recuperável na tag `sprint3-final`.

### Verificação
- Simulado numa cópia: `pytest tests` 111 passaram; `evals.guardrails_eval`
  sem falso positivo.
- `pip install -r requirements.txt` resolve as versões fixadas e os imports das
  Aulas 05–08 funcionam em Python 3.13. O `venv` local é Python 3.14: conferir
  na instalação.

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
