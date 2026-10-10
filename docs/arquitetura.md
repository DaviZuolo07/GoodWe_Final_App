# Arquitetura e fluxo — GoodWe ChargeOps (Sprint 04)

Três fluxos: **indexação** (uma vez, ou quando a base muda), **resposta** (a cada
pergunta, igual na interface, no terminal e no eval) e **avaliação** (por iteração).

## 1. Indexação — `python -m src.rag.vector_store --reindexar`

```mermaid
flowchart LR
    F["data/knowledge_base/fontes/*.md<br/>(FAQ, regimento, tarifa — elaborados pelo grupo)"]
        -- "python -m src.ferramentas.md_para_pdf base" --> P
    P["data/knowledge_base/*.pdf<br/>&lt;tipo&gt;__&lt;descricao&gt;.pdf"]
        --> L["loader.py<br/>PyMuPDFLoader · 1 Document por página<br/>categoria = prefixo do arquivo<br/>pagina = page + 1<br/>descarta capa e sumário"]
    L --> C["chunking.py<br/>RecursiveCharacterTextSplitter<br/>1000 / 150 caracteres<br/>separadores 'estrutura' (capítulo, artigo)<br/>nunca atravessa página · ID determinístico"]
    C --> E["embeddings.py<br/>nomic-embed-text (768 dims)<br/>Ollama LOCAL · prefixos search_document/search_query"]
    E --> V[("vector_store.py<br/>ChromaDB persistente em chroma_db/<br/>coleção goodwe_kb · métrica cosseno")]
```

## 2. Resposta — `ChatbotRAG` (`src/chain/rag.py`)

A mesma função atende a interface (`app/main.py`, com streaming), o terminal
(`python -m src.chain.rag`) e o eval (`evals/ragas_eval.py`). A ordem das etapas é o
acordo do `CLAUDE.md` §6: o retriever decide antes do validador de escopo.

```mermaid
flowchart TD
    U(["Pergunta do usuário<br/>(Gradio, terminal ou eval)"]) --> M{"moderation.py<br/>injection / jailbreak?"}
    M -- sim --> B["resposta fixa de bloqueio<br/>rota: bloqueio_moderacao"]
    M -- não --> EM{"emergência elétrica?<br/>(fumaça, faísca, choque)"}
    EM -- sim --> E193["resposta fixa: desligar, 193<br/>rota: recusa_escopo"]
    EM -- não --> R["retriever.py<br/>híbrido top-k=6: cosseno + BM25 (RRF)<br/>limiar 0,65 no cosseno"]
    R --> INJ["prompt_rag.trecho_suspeito<br/>tira trecho que dá ordem ao modelo<br/>(injection via documento)"]
    INJ --> T{"sobrou trecho<br/>acima do limiar?"}
    T -- não --> S["sem resposta na base"]
    T -- sim --> PR["prompt RAG versionado (v1/v2)<br/>trechos rotulados &lt;trecho documento pagina&gt;<br/>dentro de &lt;contexto_recuperado&gt; = DADO"]
    PR --> LLM["LLM · perfil 'rag'<br/>gpt-oss:120b · temperature 0 · top_p 1<br/>max_tokens 2048 · seed 42"]
    LLM --> PP["pós-processamento determinístico<br/>recusa normalizada · citação conferida<br/>canário · aviso de eletricista"]
    PP --> RC{"o modelo recusou?"}
    RC -- sim --> S
    RC -- não --> OK["resposta + (fonte: documento, página X)<br/>rota: rag"]
    S --> SV{"scope_validator<br/>jurídico / financeiro / elétrico?"}
    SV -- sim --> ENC["encaminhamento a profissional habilitado<br/>rota: recusa_escopo"]
    SV -- não --> REC["'Não encontrei essa informação<br/>nos documentos fornecidos.'"]
    OK --> UI["Interface: texto + painel 'Fontes consultadas'<br/>documento · página · categoria · score · trecho"]
    REC --> UI
    ENC --> UI
    B --> UI
    E193 --> UI
```

## 3. Avaliação — `python -m evals.ragas_eval --iteracao N`

```mermaid
flowchart LR
    ES["evals/eval_set_rag.json<br/>16 casos congelados<br/>(14 respondíveis + 2 recusa)"] --> BOT["ChatbotRAG<br/>(config da iteração)"]
    BOT --> RG["RAGAS 0.4.3<br/>faithfulness · answer_relevancy<br/>juiz gpt-oss:120b, temp 0"]
    BOT --> JM["juiz_rag.py<br/>rubrica manual 0–1 (fallback)"]
    BOT --> DT["checagens determinísticas<br/>citou? fonte certa? recusou quando devia?"]
    RR["recall_retriever.py<br/>(sem LLM) o trecho certo chegou ao top-k?"] -.diagnóstico.-> BOT
    RG --> J[("evals/resultados/ragas_N_carimbo.json<br/>scores + TODOS os parâmetros")]
    JM --> J
    DT --> J
```

## Onde cada coisa mora

| Pasta | Papel |
|---|---|
| `data/knowledge_base/` | PDFs indexados (4 categorias) e `fontes/` com o Markdown dos documentos do grupo |
| `src/rag/` | os 6 módulos do §5: loader, chunking, embeddings, vector_store, retriever, prompt_rag |
| `src/chain/rag.py` | composição LCEL do pipeline RAG (`ChatbotRAG`), com e sem streaming |
| `src/chain/llm.py` | fábrica de LLMs, perfis de parâmetros (`PERFIS`), provedores `nuvem:`/`local:` |
| `src/chain/multi_provider.py` | bônus: matriz modelo × prompt em `RunnableParallel`, nuvem + local |
| `src/guardrails/` | moderação de entrada e validação de escopo/saída (Sprint 3, inalterado) |
| `src/ferramentas/md_para_pdf.py` | Markdown → PDF (documentos do grupo e relatório de evolução) |
| `app/main.py` | interface Gradio com painel de fontes, streaming e memória por sessão |
| `evals/` | eval set, RAGAS + rubrica manual, recall do retriever, guardrails, linha de base |
| `docs/` | changelog, relatórios, briefs das fases |
| `src/app.py`, `src/chain/builder.py`, `prompts/system_prompt_v*.md` | chatbot conversacional da Sprint 3 (linha de base, mantido) |
