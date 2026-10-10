# Relatório técnico do pipeline RAG — GoodWe ChargeOps (Sprint 04)

Todos os números deste documento foram medidos em 09–10/10/2026 e estão nos arquivos
de `evals/resultados/` citados. Fluxo completo em [`arquitetura.md`](arquitetura.md).

## 1. Base de conhecimento

| Documento | Categoria | Páginas | Páginas úteis | Chunks | Origem |
|---|---|---|---|---|---|
| `manual__goodwe-hca-g2-manual-usuario.pdf` | manual | 70 | 65 | 94 | GoodWe (oficial) |
| `manual__goodwe-hca-g2-datasheet.pdf` | manual | 2 | 2 | 5 | GoodWe (oficial) |
| `manual__goodwe-hca-g2-modbus-resumo.pdf` | manual | 4 | 4 | 18 | derivado pelo grupo do protocolo oficial V1.0.15 |
| `faq__recarga-condominio.pdf` | faq | 3 | 3 | 11 | elaborado pelo grupo, a partir do manual e do datasheet |
| `regimento__condominio-modelo-recarga.pdf` | regimento | 2 | 2 | 10 | elaborado pelo grupo (condomínio fictício) |
| `tarifa__condominio-demonstracao.pdf` | tarifa | 1 | 1 | 3 | elaborado pelo grupo (R$ 2,10/kWh, cenário de demonstração) |
| **Total** | **4 categorias** | **82** | **77** | **141** | |

Página útil = página com texto (≥ 80 caracteres) que não é sumário. O sumário do manual
casava com quase toda pergunta e ocupava o top-k ("grau de proteção IP" trazia o sumário
em 1º e 2º); o loader o descarta. A categoria vem do prefixo do nome do arquivo
(`<tipo>__<descricao>.pdf`) e vira metadado no ChromaDB.

**Os documentos do grupo não inventam especificação.** O FAQ só repete o que está no
manual e no datasheet, com a seção de origem; regimento e tarifa declaram no cabeçalho
que o condomínio é fictício. A fonte de cada um está em Markdown em
`data/knowledge_base/fontes/` e o PDF é gerado por `src/ferramentas/md_para_pdf.py`, então
o conteúdo indexado é auditável pelo diff do git.

**Cortado pelo roadmap:** Lei SP 18.403/2026, IT-41 do Corpo de Bombeiros, REN 1.000 da
ANEEL e tarifa oficial da Enel (prioridades 2 e 3). Pergunta jurídica sem resposta na
base cai no encaminhamento a advogado.

## 2. Chunking

| Parâmetro | Valor | Justificativa |
|---|---|---|
| Splitter | `RecursiveCharacterTextSplitter` | padrão da Aula 06 |
| `chunk_size` | 1000 caracteres | a página mediana do manual tem ~870 caracteres: a maioria das páginas vira 1 chunk, e as tabelas do datasheet não se partem (medido abaixo) |
| `chunk_overlap` | 150 (15%) | frase cortada na fronteira aparece inteira em um dos dois chunks |
| Separadores | `["\n\n", "\nCapítulo ", "\nArt. ", "\n", ". ", " ", ""]` (estratégia `estrutura`) | ver 2.2 — foi o ganho da iteração 2 |
| Fronteira | nunca atravessa página | cada chunk tem uma página só; a citação nunca aponta a página errada |
| Limpeza | espaços, linhas em branco e ligaduras tipográficas (ﬁ → fi) | o PDF gerado pelo PyMuPDF devolve "ﬁ"; "ﬁctício" e "fictício" seriam tokens diferentes |
| ID | `documento:p<pagina>:c<n>` | reindexar não duplica, e o chunk citado na iteração 1 é o mesmo na 2 |

### 2.1 Comparação de `chunk_size` (Aula 07)

Mesmo corpus, prompt v1, k=4, separadores da aula, overlap = size/8 (exceto 1000/150),
RAGAS com juiz `gpt-oss:120b`. Arquivos `ragas_chunk*.json` e `ragas_1_*.json`.

| chunk / overlap | Chunks | Faithfulness | Answer relevancy | Taxa de resposta | Fonte certa citada | Tokens de entrada/turno | Recusou indevidamente |
|---|---|---|---|---|---|---|---|
| 256 / 32 | 446 | 0,905 | 0,594 | 78,6% | 71,4% | 858 | M01, M04, R03 |
| 512 / 64 | 233 | 0,905 | 0,663 | 85,7% | 78,6% | 1.059 | R01, R03 |
| 1024 / 128 | 137 | 0,881 | 0,646 | 92,9% | 92,9% | 1.399 | R01 |
| **1000 / 150** (iteração 1) | 139 | 0,875 | 0,714 | 92,9% | 92,9% | 1.419 | R01 |

Chunk pequeno parte as tabelas: com 256, "potência nominal do GW22K-HCA-20" (M01) é
recusada porque o rótulo da linha e o valor caem em chunks diferentes. O faithfulness
sobe um pouco com chunk menor (menos texto para o modelo extrapolar), mas a taxa de
resposta cai. 1000 ficou como tamanho.

### 2.2 Separadores por estrutura — o ganho da iteração 2

Diagnóstico da iteração 1: R01 ("por quanto tempo posso reservar a vaga?") recusado e R02
("tolerância de atraso?") respondido com o artigo vizinho. Causa medida com
`python -m evals.recall_retriever` (sem LLM: a evidência literal da resposta chegou ao
top-k?): o Capítulo IV do regimento (Art. 8–10) não tinha chunk próprio. Vinha colado ao
Art. 7 (cartão RFID), e o embedding do chunk misto "falava de cartão": 7º lugar para R01 e
21º, abaixo do limiar, para R02.

| Separadores | chunk 256, k=4 | 512, k=4 | **1000, k=4** | 512, k=8 | 1000, k=8 |
|---|---|---|---|---|---|
| aula `["\n\n", "\n", ". ", " ", ""]` | 0,643 | 0,857 | 0,857 | 0,929 | 0,929 |
| estrutura (+ `"\nCapítulo "`, `"\nArt. "`) | 0,643 | 0,929 | **1,000** | 1,000 | 1,000 |

Recall do retriever nos 14 casos respondíveis (`evals/resultados/recall_retriever.json`).
Com a estrutura, cada chunk começa e termina em fronteira de artigo: recall 1,000 **com o
mesmo tamanho de chunk, o mesmo k e o mesmo custo de tokens**. Aumentar k para 8 sem mudar
os separadores chegava a 0,929 e dobrava o contexto.

## 3. Embeddings e vector store

- `nomic-embed-text` (768 dimensões) no **Ollama local**, com os prefixos
  `search_document:` / `search_query:` do model card. A Ollama Cloud responde 401 em
  `/api/embed` para esta conta; o modelo é o pedido pelo §3, só o host muda.
- ChromaDB persistente em `chroma_db/` (gitignored, regenerável com `--reindexar`),
  coleção `goodwe_kb`, métrica **cosseno** (`hnsw:space = cosine`): o score de relevância
  fica em [0, 1] e o limiar é interpretável.

## 4. Retriever

| Parâmetro | Valor | Justificativa medida |
|---|---|---|
| Busca | **híbrida** desde a iteração 3: cosseno (`similarity_search_with_relevance_scores`) + BM25 sobre os mesmos chunks, fundidos por Reciprocal Rank Fusion (k=60). Iterações 1 e 2: só cosseno | ver 4.1 |
| k | **6** desde a iteração 3 (4 nas iterações 1 e 2) | recall 1,000 no eval set com k 4 e com k 6; no eval set de robustez, k 6 responde 0,917 contra 0,875 de k 4; ~1.800 tokens de entrada por turno |
| Limiar | 0,65, sempre sobre o **cosseno** | ver abaixo |

**Por que 0,65 e não 0,75** (o 0,75 é a heurística da Aula 05). Na calibração de
09/10/2026, as perguntas respondíveis tinham o melhor chunk entre 0,704 e 0,846, e as fora
da base entre 0,624 e 0,820: as faixas se sobrepõem, porque similaridade mede assunto, não
presença da resposta. Com 0,75 o bot recusaria perguntas boas (0,704). O limiar baixo só
corta o claramente fora de assunto (aí o LLM nem é chamado); a recusa fina fica com o
prompt, que devolve a frase literal quando os trechos não contêm a resposta. Nos 2 casos
de recusa do eval set, as duas camadas juntas acertaram 2/2 em todas as execuções.

### 4.1 Busca híbrida — o ganho da iteração 3

**Problema achado no uso, não no eval.** Na interface, "Qual a potência do GW22K-HCA-20"
(sem "nominal de saída") recebeu a recusa. O eval set do RAGAS tem perguntas longas e
específicas e estava em 100% de resposta; a pergunta curta de morador não estava lá. O
diagnóstico: o datasheet caiu para o 5º lugar, atrás de quatro páginas de **desenho de
dimensão** do manual que repetem o código do modelo. "Qual o peso do carregador?" e "qual o
grau de proteção?" nem chegavam ao top-12: a tabela técnica tem ~40 campos num chunk, e o
embedding dela é a média de todos.

**O que foi medido antes de mudar.** Criamos `evals/eval_set_robustez.json` (24 perguntas
curtas, com a evidência literal de cada uma) **separado** do eval set do RAGAS, que continua
congelado (acrescentar casos mudaria a régua das iterações 1 e 2). Testamos, sem LLM, três
alternativas: sub-trechos pequenos para a busca com o chunk inteiro para o modelo (recall
0,458 → 0,708 com BM25, mas sobe o score de perguntas fora da base e enfraquece o limiar);
janelas só nos chunks de tabela (0,708, idem); extração de tabela do PyMuPDF (células
duplicadas, e não detecta a tabela do datasheet). Ficou a mais simples: **BM25 + vetor com
RRF**, sem dependência nova e sem mudar o índice.

| Busca (eval set de robustez, 24 perguntas de morador) | Recall do retriever | Taxa de resposta | Fato na fonte citada |
|---|---|---|---|
| Vetorial, k 4 (config. da iteração 2) | 0,375 | 0,625 | 0,375 |
| Híbrida (BM25 + vetor, RRF), k 4 | 0,625 | 0,875 | 0,625 |
| **Híbrida, k 6 (iteração 3, entregue)** | **0,667** | **0,917** | **0,667** |

"Fato na fonte citada" = a resposta cita (documento, página) de um trecho que contém a
evidência literal, ou a própria resposta a contém (`python -m evals.robustez_eval`). É
estrito: "22 kW (trifásico)" citando o regimento responde N01 corretamente mas não conta,
porque a evidência é o "22000" do datasheet. As 8 respostas que não contaram foram lidas
uma a uma: 6 corretas por outra fonte, 2 recusas (dimensões; multa do regimento, cujo
trecho ficou em 0,649, logo abaixo do limiar). **Nenhuma invenção.** O limiar continua
sobre o cosseno: a fusão só decide a ordem, então uma pergunta fora de assunto que repete
uma palavra da base não ganha contexto pelo BM25. Arquivos: `recall_robustez_20261010_114321.json`,
`robustez_denso_k4_20261010_114634.json`, `robustez_hibrido_k4_20261010_114726.json`,
`robustez_hibrido_k6_20261010_114726.json`.

## 5. Grounding e citação

Três mecanismos no prompt (`src/rag/prompt_rag.py`, v1) e um determinístico depois dele:

1. **"Responda SOMENTE com informações presentes nos trechos"** e "número que não está
   nos trechos não existe" (regras 1 e 4).
2. **Recusa literal:** sem resposta nos trechos, exatamente "Não encontrei essa informação
   nos documentos fornecidos." A chain normaliza qualquer variação para a frase exata.
3. **Citação copiada do rótulo:** cada trecho entra como
   `<trecho n="1" documento="…" pagina="…">`, com `pagina = page + 1` calculado no loader.
   O modelo copia o rótulo em vez de deduzir a página do texto (o rodapé impresso do manual
   não é a página do PDF).
4. **Pós-processamento:** resposta sem citação recebe a do melhor trecho
   (`citacao_adicionada`); citação de documento/página que não veio do retriever é
   registrada (`citacoes_invalidas`). Nas execuções finais: citação em 100% das respostas,
   0 citações inválidas.

## 6. Segurança

| Ameaça | Defesa | Medição |
|---|---|---|
| Injection/jailbreak na pergunta | `moderation.py` antes de tudo | `python -m evals.guardrails_eval`: 39/39 bloqueados, 0 falsos positivos em 44 legítimas |
| Injection **via documento** (PDF da base com "ignore as instruções") | (a) contexto entre `<contexto_recuperado>`, declarado como DADO; (b) marcadores do prompt neutralizados dentro do texto do chunk; (c) `trecho_suspeito` tira do contexto o chunk que dá ordem ao modelo | `python -m evals.injecao_documento_eval`: 3/3 com o filtro; 3/3 só com o prompt (`--sem-filtro`); 0 falsos positivos nos 141 chunks reais |
| Pergunta fora da base | limiar + recusa literal | `recusa_correta` 2/2 em todas as iterações |
| Jurídico, financeiro, elétrico sem resposta na base | `scope_validator` depois do retriever (CLAUDE.md §6) | 11/11 com encaminhamento a profissional habilitado |
| Especificação inventada | regras 1 e 4 do prompt + temperature 0 | faithfulness 0,976 na iteração 2 e 1,000 na iteração 3 |

## 7. Avaliação

`python -m evals.ragas_eval --iteracao N` roda o eval set congelado
(`evals/eval_set_rag.json`: 16 casos, 4 categorias + 2 de recusa) e grava os scores com
todos os parâmetros. Três medidas, na mesma execução: RAGAS (faithfulness,
answer_relevancy), rubrica manual 0–1 (`evals/rubrica_manual.md`) e checagens
determinísticas (citou? fonte certa? recusou quando devia?).

| Execução | Config | Faithfulness | Answer relevancy | Fidelidade manual | Relevância manual | Resposta | Fonte certa | Recusa |
|---|---|---|---|---|---|---|---|---|
| **Iteração 1** | v1, chunk 1000/150, separadores aula, k 4 | 0,875 | 0,714 | 1,00 | 0,93 | 92,9% | 92,9% | 2/2 |
| **Iteração 2** | v1, chunk 1000/150, separadores **estrutura**, k 4 | **0,976** | **0,780** | 1,00 | 1,00 | **100%** | **100%** | 2/2 |
| Iteração 2, repetição | idem | 0,976 | 0,742 | 1,00 | 1,00 | 100% | 100% | 2/2 |
| Iteração 2b | + prompt **v2** | 0,976 | 0,753 | 1,00 | 1,00 | 100% | 100% | 2/2 |
| **Iteração 3** (entregue) | v1, chunk 1000/150, estrutura, **busca híbrida, k 6** | **1,000** | 0,789 | 1,00 | 0,96 | 100% | 100% | 2/2 |

Juiz `gpt-oss:120b`, temperature 0, seed 42, embeddings `nomic-embed-text`, mesmo eval set
em todas. Arquivos: `ragas_1_20261010_002052.json`, `ragas_2a_20261010_003243.json`,
`ragas_2a-repeticao_20261010_003646.json`, `ragas_2_20261010_003438.json`,
`ragas_3_20261010_115329.json`.

**Leitura honesta da iteração 3.** No eval set congelado ela não regride, e o ganho é
pequeno: faithfulness 0,976 → 1,000 e answer_relevancy 0,789, dentro da faixa de ruído
medida (0,742–0,780 em duas execuções idênticas da iteração 2). A relevância manual caiu de
1,00 para 0,96 (um caso com nota 0,5) e o contexto subiu de ~1.510 para ~1.815 tokens por
turno. O ganho que justifica a mudança está nas perguntas que o eval set não tinha
(seção 4.1): taxa de resposta 0,625 → 0,917.

**Pergunta de score baixo analisada — F02** ("Encostei o cartão e a luz vermelha acendeu
por 2 segundos. O que fiz de errado?"), answer_relevancy 0,44–0,46 em todas as execuções,
com faithfulness 1,0 e fonte certa. Os chunks vieram certos (FAQ pág. 1, manual pág. 21) e
a resposta está correta ("o cartão foi encostado antes de conectar o plugue"). O
answer_relevancy gera perguntas a partir da resposta e compara por embedding com a
original; "o que fiz de errado?" é uma pergunta sobre o usuário, e a resposta descreve a
sequência de uso, então as perguntas geradas ("qual a ordem correta para usar o cartão?")
ficam longe da original no espaço vetorial. É limite da métrica para perguntas indiretas,
não falha do sistema — a rubrica manual deu 1,0. Para melhorar o número sem enganar a
métrica, a resposta teria de repetir a forma da pergunta ("Você encostou o cartão antes
de…"), o que o v2 tentou (resposta direta) sem ganho medido.

**Régua 0 (descartada).** A primeira execução passou ao RAGAS o texto cru dos chunks, sem o
rótulo `[documento, página]` que o modelo recebe. O RAGAS tratou a citação como afirmação
sem suporte: T01 (um fato + uma citação) tirou 0,5; M03 (um fato + duas citações), 0,0;
faithfulness médio 0,664 contra 1,0 do juiz manual. A régua foi corrigida e a iteração 1
reexecutada (invariante 6: mudou a régua, as duas pontas reexecutam). Registro em
`ragas_1-regua0_20261010_001705.json`.

## 8. Divergências deliberadas das aulas

| Aula usa | Aqui usamos | Por quê |
|---|---|---|
| `langchain_community.vectorstores.Chroma` | `langchain_chroma.Chroma` | o pacote dedicado é o pin do projeto; API idêntica (`from_documents`, `as_retriever`, `similarity_search_with_score`) |
| `google.colab.userdata.get(...)` | `os.getenv(...)` via `python-dotenv` | projeto é local, não notebook (§1 do enunciado) |
| `qwen3.6:27b` | `gpt-oss:120b` + `gemma4:31b` | já medidos na linha de base da Sprint 3; são os 2+ modelos do bloco C. O `kimi-k2.6`, escolhido pelo grupo, exige créditos na Ollama Cloud desta conta |
| `persist_directory="/content/..."` | `chroma_db/` na raiz | gitignored, regenerável |
| `nomic-embed-text` na Ollama Cloud | `nomic-embed-text` no Ollama local | a nuvem responde 401 em `/api/embed` |
| limiar 0,75 (Aula 05) | 0,65 | calibrado no corpus (seção 4) |
| `PyPDFLoader` (Aula 05) | `PyMuPDFLoader` | o enunciado (§3) pede PyMuPDF; mantém o número de página |
| Python do Colab | Python 3.13 | `ragas 0.4.3` não instala no 3.14 sem o Microsoft C++ Build Tools (`scikit-network`) |
