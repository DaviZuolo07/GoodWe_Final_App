# Changelog — Sprint 04

## Passo 0 — Git limpo, ambiente e kit de trabalho (09/10/2026)

### O que mudou
- Backup integral em `..\GoodWe_BACKUP_09102026` antes de qualquer ação.
- `git fetch --prune`: `origin/feature/*` (ai-davi, backend-crepe, frontend-gus)
  já não existiam no GitHub. As três locais apontavam para o commit raiz `18266c0`,
  sem trabalho próprio, e foram apagadas com `git branch -d`.
- Tag `sprint3-final` (`bc3e78f`) publicada no GitHub — era a única cópia das
  Sprints 1–3 e só existia no disco local.
- Os 62 arquivos não rastreados (legado das Sprints 1–3 que a F0 tirou do índice)
  foram conferidos um a um contra a tag: **todos idênticos byte a byte**. Em vez de
  `git clean -fd`, foram **movidos** para `..\GoodWe_QUARENTENA_legado_09102026`
  (reversível; a tag continua sendo a cópia oficial).
- `main` local estava em `18266c0`; avançou para `develop` e recebeu o merge de
  `origin/main` (PR #1, cuja árvore é a da F0). Resultado: `main` e `develop` no
  mesmo commit de merge `c53eb7d`, 54 arquivos rastreados, diff vazio entre as duas.
- `venv` estava sem metade da stack da Sprint 04 (sem `langchain-classic`, chroma,
  ragas, gradio; `langchain-core` em 1.6.7 contra o pin 1.6.1) e o `pytest` quebrava
  na coleta. Reinstalado com `pip install -r requirements.txt`: `pip check` limpo e
  imports das Aulas 05–08 funcionando **em Python 3.14** (os pins também valem aqui).
- `.env` reconstruído a partir do `.env.example`, com `EMBEDDING_MODEL` e
  `CHROMA_DIR`. O anterior está em `.env.backup-local` (ignorado por `.env.*`).
- Instalados na raiz: `CLAUDE.md`, `ROADMAP_SOLO.md`, `PASSO_0.md`.
- Identidade git do repositório: `DaviZuolo07 <davi.zuolo07@gmail.com>` (a máquina
  não tinha `user.name` configurado).

### Em aberto
- **Chave do Ollama não foi trocada (0.1).** O `.env` novo ainda usa a chave que
  vazou. Revogar em https://ollama.com/settings/keys e colar a nova.
- `docs/briefs/` (5 briefs das fases) ainda não está no repositório.
- 0.8: os outros três integrantes ainda precisam configurar `user.name`/`user.email`
  e commitar (`git shortlog -sn` hoje mostra só um nome).

### Achados (viram tarefa)
- **`nomic-embed-text` NÃO está disponível no Ollama Cloud desta conta.** Não aparece
  entre os 18 modelos do `teste_auth`, e `POST /api/embed` responde **401** para
  qualquer modelo de embedding com a mesma chave que o `/api/chat` aceita. No Ollama
  local o modelo também não está baixado (404). Proposta: embeddings no Ollama local
  (`ollama pull nomic-embed-text`) — mantém o modelo pedido no §3 e muda só o host de
  embedding. **Decisão do grupo, afeta a F1/F2.**
- A `origin/main` rastreava `evals/resultados/*.json` e `docs/modelos_disponiveis.json`,
  que hoje estão no `.gitignore`; o merge desta fase os retirou da `main`.

### Verificação
```
> git ls-remote --tags origin
bc3e78f528d848e265bb26198a1b1b7a953de8e0	refs/tags/sprint3-final

> git check-ignore -v .env .env.backup-local
.gitignore:22:.env	.env
.gitignore:23:.env.*	.env.backup-local

> git ls-files | find /c /v ""
54

> python -m pytest tests -q
111 passed in 1.22s

> python -m evals.guardrails_eval
  "bloqueados": 39, "taxa_bloqueio_pct": 100.0, "legitimas": 44,
  "falsos_positivos": 0, "taxa_falso_positivo_pct": 0.0,
  "restritos_com_encaminhamento": "11/11"

> python -m src.teste_auth   (seção 5)
  18 modelo(s): ... gemma4:31b, gpt-oss:120b <- principal, gpt-oss:20b ...
  (nomic-embed-text ausente)
```

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
