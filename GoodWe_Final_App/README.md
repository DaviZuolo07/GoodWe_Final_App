# 🔋 GoodWe ChargeOps AI Assistant

> Chatbot de recarga de veículos elétricos em condomínios — **EV Challenge 2026 · FIAP × GoodWe**
> Disciplina *Prompt and Artificial Intelligence* · 2º semestre de Ciência da Computação · 2026.2

---

## 👥 Integrantes

| Nome | RM |
|---|---|
| Davi Q. Zuolo | 571669 |
| Gustavo Zagato | 569420 |
| Daniel Vilela Mana | 571632 |
| Kayo Henderson | 570706 |

> A divisão de trabalho da Sprint 03 fica em [`docs/equipe.json`](docs/equipe.json) e entra
> automaticamente no relatório em PDF.

---

## 📌 Sobre o Projeto

O **GoodWe ChargeOps AI Assistant** é um chatbot para o ecossistema **ChargeGrid Intelligence /
EV ChargeOps**: recarga de veículos elétricos em condomínios, operação dos carregadores e
faturamento por kWh. Ele atende **moradores, síndicos, operadores e visitantes**.

### 🔁 Evolução do projeto

| Sprint | O que foi feito |
|---|---|
| **1** | Definição do problema, escopo, personas, escolha do modelo e roteiro de 5 perguntas-teste. |
| **2** | Chatbot funcional em Python: *system prompt*, histórico em SQLite, perfis de usuário, interface Streamlit. Código em `ai/`. |
| **3 (atual)** | **Refactory do núcleo conversacional para LangChain LCEL**, com memória por sessão limitada por tokens, saída estruturada Pydantic v2, context engineering e guardrails — tudo medido contra a versão anterior. Código em `src/`, `prompts/` e `evals/`. |

### ⚖️ A regra que organiza esta sprint

> **A pasta `ai/` não é alterada.** Ela é o **grupo de controle** do comparativo antes/depois
> exigido no §8 do contrato. Todo o código novo vive em `src/`, `prompts/` e `evals/`.
> Auditado com `diff -rq`: nenhuma diferença.

---

## ⚡ Sprint 03 — o que o contrato pede e onde está

| # | Item do escopo | Implementação |
|---|---|---|
| 1 | Chain LCEL `ChatPromptTemplate \| ChatOllama (gpt-oss:120b) \| parser` | [`src/chain/builder.py`](src/chain/builder.py), [`src/chain/llm.py`](src/chain/llm.py) |
| 2 | Memória por sessão: `RunnableWithMessageHistory` + `ConversationTokenBufferMemory`, limite de tokens, 3+ turnos | [`src/chain/memoria.py`](src/chain/memoria.py), [`evals/memoria_demo.py`](evals/memoria_demo.py) |
| 3 | Structured output Pydantic v2 (`ConsultaRecarga`) com `field_validator` | [`src/schemas/consulta_recarga.py`](src/schemas/consulta_recarga.py) |
| 4 | Context engineering: prompt versionado com XML tagging + tiktoken | [`prompts/`](prompts/), [`src/chain/prompts.py`](src/chain/prompts.py), [`src/chain/tokens.py`](src/chain/tokens.py) |
| 5 | Segurança e guardrails: jailbreak, injection, escopo GoodWe | [`src/guardrails/`](src/guardrails/) |
| 6 | Eval reexecutado + relatório de evolução (PDF) | [`evals/`](evals/), [`docs/relatorio_evolucao.pdf`](docs/relatorio_evolucao.pdf) |
| ➕ | **Bônus (+1)**: multi-provider — vários modelos × vários prompts | [`src/chain/multi_provider.py`](src/chain/multi_provider.py) |

**Fora do escopo desta sprint, de propósito:** LangGraph, agentes, function calling, RAG e
observabilidade pertencem aos Módulos 3 e 4 (§3 do contrato). A interface Streamlit da Sprint 03
existe para **demonstrar e testar**, não como item de escopo.

---

## 🗺️ Arquitetura de um turno

```
pergunta
   │
   ├─► moderação (injection, jailbreak, dados de terceiros, fraude)
   ├─► validação de escopo (jurídico, financeiro, elétrico, produto fora da base, off-topic)
   │
   └─► RunnableBranch
          ├── bloqueado ──► resposta fixa, auditável, 0 chamadas ao LLM
          └── liberado ──► extração estruturada (Pydantic v2, com autocorreção)
                        ──► cálculo determinístico em Python
                        ──► [prompt vN | ChatOllama | StrOutputParser] + memória por sessão
                        ──► validação de saída (canário, tags internas, instrução elétrica)
```

### 🧮 O LLM extrai, o Python calcula

O modelo **não faz conta**. Ele preenche o schema `ConsultaRecarga`; a calculadora
([`src/dominio/recarga.py`](src/dominio/recarga.py)) produz tempo, energia e custo, e o resultado
entra no prompt como `<calculo_verificado>`. A eficiência de recarga AC usada é de **89,4%**
(faixa de 85,7% a 92%), medida por Sears, Roberts & Glitman (IEEE SusTech, 2014) —
fórmulas, fontes e conferências manuais em [`docs/fundamentacao_calculos.md`](docs/fundamentacao_calculos.md).

Exemplo conferido à mão: 60 kWh, de 20% a 100%, em 7,4 kW → 48 kWh na bateria ÷ (7,4 × 0,894) =
**7h15**, apresentado como estimativa com faixa.

### 🛡️ Guardrails em duas camadas

1. **Determinística, antes do LLM** — regras auditáveis (qual regra bloqueou e por quê), resposta fixa e custo zero. Trata ofuscação por leetspeak, base64, letras espaçadas, caracteres invisíveis e inglês.
2. **No prompt v2** — a pergunta do usuário é isolada em `<pergunta_usuario>` (*spotlighting*) e o prompt carrega um **canário**: se ele aparecer na resposta, houve vazamento e a saída é substituída.

Recusas de domínio restrito sempre encaminham: advogado, contador ou consultor financeiro,
eletricista habilitado (NBR 5410 e NBR 17019) ou assistência técnica autorizada.

---

## 📁 Estrutura do projeto

```
GoodWe_Final_App/
├── src/                          # SPRINT 03 — núcleo novo
│   ├── app.py                    # chatbot no terminal (/memoria, /extrair, --detalhes, --trace)
│   ├── diagnostico.py            # checagem do ambiente -> docs/ambiente.md
│   ├── teste_auth.py             # diagnóstico de credencial camada por camada
│   ├── chain/
│   │   ├── builder.py            # pipeline LCEL completo (ChatbotChargeOps)
│   │   ├── llm.py                # fábrica de LLM: perfis, provedores, fallback
│   │   ├── memoria.py            # ConversationTokenBufferMemory + RunnableWithMessageHistory
│   │   ├── prompts.py            # carregador de prompts versionados + canário
│   │   ├── tokens.py             # régua o200k_harmony (tokenizador do gpt-oss)
│   │   ├── multi_provider.py     # bônus: matriz modelo × prompt em RunnableParallel
│   │   └── hello_lcel.py         # "hello world" do LCEL (didático)
│   ├── schemas/
│   │   ├── consulta_recarga.py   # schema do domínio EV + field_validators
│   │   └── resultados.py         # CalculoRecarga, VereditoJuiz, RespostaTurno
│   ├── dominio/recarga.py        # calculadora determinística (fundamentada)
│   ├── guardrails/
│   │   ├── moderation.py         # injection, jailbreak, privilégio, fraude
│   │   └── scope_validator.py    # escopo GoodWe, domínios restritos, validação de saída
│   └── ui/streamlit_app.py       # interface de demonstração e testes (Sprint 03)
├── prompts/                      # system prompts versionados
│   ├── system_prompt_v1.md       # consolidado em markdown
│   ├── system_prompt_v2.md       # XML tagging + spotlighting + canário
│   ├── base_produtos.json        # ÚNICA fonte de especificação de produto
│   └── README.md                 # tabela de versões com ganho medido (gerada)
├── evals/                        # avaliação
│   ├── eval_set.json             # 28 casos congelados (v1.1)
│   ├── structured_set.json       # 15 casos com gabarito para o structured output
│   ├── guardrails_set.json       # 39 ataques + 44 perguntas legítimas
│   ├── runner.py                 # executa o eval e grava métricas por caso
│   ├── adaptadores.py            # legado | lcel_cru | lcel | falso
│   ├── pontuacao.py              # checagem determinística (régua v1.1)
│   ├── juiz.py                   # juiz LLM com saída Pydantic
│   ├── structured_eval.py        # acurácia do structured output (manual × LCEL)
│   ├── guardrails_eval.py        # bloqueio e falso positivo (offline)
│   ├── memoria_demo.py           # demonstração de memória em 6 turnos
│   ├── multi_provider (em src)   # bônus
│   ├── executar_tudo.py          # bateria completa em um comando
│   ├── gerar_relatorios.py       # gera tabelas, relatórios e PDF a partir dos resultados
│   ├── relatorio_pdf.py          # relatório de evolução (§8)
│   ├── validar_entrega.py        # checklist automático da rubrica
│   └── resultados/               # um JSON por execução (rastreabilidade)
├── tests/                        # 122 testes offline (pytest)
│   ├── test_schema_e_calculo.py
│   ├── test_guardrails.py
│   ├── test_pipeline_offline.py
│   ├── test_pontuacao.py
│   ├── test_ui_streamlit.py      # renderização das 7 páginas (AppTest)
│   └── servidor_ollama_falso.py  # servidor Ollama falso para ensaios sem cota
├── ai/                           # SPRINT 2 — INTOCADO (grupo de controle)
├── database/                     # SQLite da Sprint 2
├── docs/                         # relatórios e guias (ver índice abaixo)
├── .streamlit/config.toml        # tema GoodWe
├── .env.example                  # variáveis (o .env real não é versionado)
├── requirements.txt              # dependências da Sprint 2
└── requirements-sprint3.txt      # dependências da Sprint 03 (versões fixadas)
```

---

## 🚀 Como Executar o Projeto

### 1. Ambiente

```bash
python -m venv venv
venv\Scripts\activate            # Linux/Mac: source venv/bin/activate
pip install -r requirements-sprint3.txt
cp .env.example .env               # cole a OLLAMA_API_KEY de ollama.com/settings/keys
```

### 2. Interface visual (recomendado para demonstrar)

```bash
streamlit run src/ui/streamlit_app.py
```

Sete painéis, com a identidade visual do painel ChargeOps:

| Painel | O que mostra |
|---|---|
| **Assistente IA** | conversa com telemetria por turno: rota, chamadas ao LLM, tokens locais e **tokens contados pelo servidor**, latência, cálculo verificado, extração e o prompt exato enviado |
| **Memória da sessão** | tokens na janela, podas, mensagens descartadas e os fatos que sobrevivem à poda |
| **Extração estruturada** | escreve uma frase, vê o JSON validado pelo Pydantic e o cálculo derivado |
| **Guardrails** | testa qualquer frase e vê a regra acionada; roda o eval de guardrails na hora |
| **Prompts e tokens** | comparação de tokens (legado × v1 × v2), conteúdo das versões e contador tiktoken |
| **Modelos** | parâmetros por perfil e comparação multi-provider (bônus) |
| **Avaliação** | tabela antes/depois, leitura caso a caso do eval e checklist da entrega |

### 3. Terminal

```bash
python -m src.app --perfil-demo --detalhes     # conversar com telemetria
python -m src.app --trace                      # ver cada passo da chain (set_debug)
```

Comandos na conversa: `/memoria`, `/extrair`, `/limpar`, `/sair`.

### 4. Verificar se a LLM está sendo chamada de verdade

Com `--detalhes` (ou no painel Assistente), cada turno mostra:

```
[rota=llm guardrail=None chamadas_llm=2 tokens_locais=1876+22 estruturado=True]
[servidor: 1666 entrada + 67 saida = 1733 tokens  <- contados PELO MODELO: a chamada foi real]
```

Os tokens locais são contados na sua máquina com tiktoken e aparecem mesmo sem rede. Os tokens
do servidor vêm do `usage_metadata` do Ollama: **se forem zero, nenhuma chamada real chegou ao
modelo**. Em um ataque, o esperado é `chamadas_llm=0` — ali o guardrail resolve sozinho.

### 5. Testes e avaliação

```bash
python -m pytest tests -q            # 122 testes offline, sem chave (~3 s)
python -m evals.guardrails_eval      # 39/39 bloqueios, 0/44 falso positivo
python -m src.teste_auth             # diagnóstico de credencial
python -m evals.executar_tudo        # bateria completa + todos os relatórios + PDF
python -m evals.validar_entrega      # checklist da rubrica (A, B, C, D, bônus, §10)
```

Para ensaiar sem gastar cota: `python -m tests.servidor_ollama_falso` e rode com
`OLLAMA_HOST=http://127.0.0.1:11999`. Os números desse modo **não valem** como resultado.

### 6. Interface da Sprint 2 (comparação)

```bash
pip install streamlit
streamlit run ai/ui/streamlit_app.py
```

---

## 🧪 Avaliação — como o ganho é provado

O mesmo eval set roda em quatro configurações, com o mesmo runner, a mesma régua de pontuação e
o mesmo juiz:

| Coluna | O que isola |
|---|---|
| `legado` | Sprints 1/2, código de `ai/` sem alteração |
| `lcel_cru` | efeito do **framework sozinho** (prompt genérico, sem guardrails) |
| `lcel v1` | + prompt versionado |
| `lcel v2` | + XML tagging, structured output, cálculo verificado e guardrails |

Há ainda uma **ablação** (`v2` sem guardrails) para separar o que veio do prompt do que veio das
regras. O juiz é o `glm-5.3-flash`, **fora** dos modelos avaliados, para evitar viés de
auto-preferência. Saídas: `evals/sprint3_results.json`, `docs/tabela_antes_depois.md`,
`docs/relatorio_modelos.md`, `prompts/README.md` e `docs/relatorio_evolucao.pdf`.

### Medições que não dependem de chave de API

| Medida | Valor |
|---|---|
| Tokens fixos por chamada: legado → v1 → v2 | **3.700 → 307 → 989** (régua `o200k_harmony`) |
| Instrução de formato do Pydantic: padrão → compacta | **1.060 → 508** tokens |
| Guardrails: bloqueio · falso positivo · encaminhamento | **39/39 · 0/44 · 11/11** |
| Casos do eval resolvidos sem chamar o LLM | **14 de 28** |
| Turno médio da Sprint 2 (base do limite de memória) | 174 tokens → 1.200 cobre ≈6,9 turnos |
| Testes offline | **122 passando** |

> Qualidade, latência e acurácia do structured output dependem de rodar com chave. Enquanto não
> rodam, as células aparecem como **"pendente"** — nenhum número é estimado.

---

## 📄 Documentação

| Documento | Conteúdo |
|---|---|
| [`docs/COMO_TESTAR.md`](docs/COMO_TESTAR.md) | fluxo de teste passo a passo, do zero à entrega |
| [`docs/VALIDACAO.md`](docs/VALIDACAO.md) | o que validar à mão, critérios de aprovação e sinais de alarme |
| [`docs/AUDITORIA_SPRINT3.md`](docs/AUDITORIA_SPRINT3.md) | auditoria contra o contrato e as aulas, achados e riscos residuais |
| [`docs/RELATORIO_MUDANCAS.md`](docs/RELATORIO_MUDANCAS.md) | o que mudou nesta sprint, arquivo por arquivo |
| [`docs/fundamentacao_calculos.md`](docs/fundamentacao_calculos.md) | fórmulas, fontes acadêmicas e conferências manuais |
| [`docs/relatorio_evolucao.pdf`](docs/relatorio_evolucao.pdf) | relatório de evolução (§8), até 5 páginas |
| [`docs/tabela_antes_depois.md`](docs/tabela_antes_depois.md) · [`docs/relatorio_modelos.md`](docs/relatorio_modelos.md) · [`prompts/README.md`](prompts/README.md) | gerados a partir dos resultados |
| [`docs/test_cases.md`](docs/test_cases.md) | os 5 casos da Sprint 2 (origem dos casos S12 do eval) |
| `docs/agents/`, `docs/architecture/`, `docs/database/` | documentação de domínio da Sprint 2 |

---

## ⚠️ Limitações declaradas

- Guardrails por regra não cobrem paráfrase criativa infinita — por isso existem o prompt v2 e o validador de saída.
- As 44 perguntas legítimas foram escritas junto com as regras: o 0% de falso positivo tem viés de autor.
- 28 casos são amostra pequena; diferenças de poucos pontos entre modelos não são conclusivas.
- O juiz é um LLM e também erra; divergências entre juiz e checador são sinalizadas caso a caso.
- Eficiência DC e desaceleração acima de 80% em DC são **premissas declaradas**, não medições.
- `ConversationTokenBufferMemory` e `RunnableWithMessageHistory` estão marcadas como deprecated no LangChain 1.x; foram mantidas porque o escopo da sprint as exige.

---

# 📚 Sprints 1 e 2 — documentação da versão legada (`ai/`)

> Mantida na íntegra: é o grupo de controle do comparativo desta sprint.

## 🗄️ Banco de Dados (SQLite)

**Tecnologia:** SQLite
**Arquivo:** `database/goodwe.db` (gerado automaticamente, não deve ser versionado)

### Arquivos da camada de persistência

- **`database/connection.py`**: gerencia a conexão com o arquivo `goodwe.db` (abre/fecha conexões SQLite).
- **`database/schema.sql`**: script SQL com a definição das tabelas (`users`, `chats`, `messages`) e seus relacionamentos.
- **`database/init_db.py`**: executa o `schema.sql` na primeira vez, criando o banco do zero caso ele não exista.
- **`database/chat_persistence_service.py`**: camada de serviço de persistência — é quem o `chat_service.py`/UI chama para salvar usuários, conversas e mensagens, sem precisar saber SQL.
- **`database/repositories/`**: camada de acesso direto ao banco (executa SQL puro):
  - **`user_repository.py`**: insere, busca e atualiza usuários na tabela `users`.
  - **`chat_repository.py`**: cria e busca conversas na tabela `chats`.
  - **`message_repository.py`**: insere e busca mensagens na tabela `messages`.

### 🔄 Como a UI se conecta ao banco (fluxo de dados)

1. Usuário preenche **login/cadastro** no `streamlit_app.py`.
2. Os dados são enviados para `ChatPersistenceService.create_user_if_not_exists()`.
3. Esse serviço chama `user_repository.py`:
   - Procura o usuário pelo nome.
   - Se não existir → cria novo registro na tabela `users`.
   - Se existir → reutiliza o cadastro já salvo.
4. Ao iniciar uma conversa, `create_chat()` cria um novo registro na tabela `chats`, vinculado ao `user_id`.
5. A cada mensagem (do usuário e da IA), `message_repository.py` insere um registro na tabela `messages`, vinculado ao `chat_id`.
6. Quando o usuário volta a abrir uma conversa, `conversation_memory.py` **lê as mensagens do banco** e reconstrói o histórico, dando à IA "memória" do que já foi conversado.

### 📊 Estrutura das Tabelas

**`users`**
| Campo | Descrição |
|---|---|
| id | Identificador único |
| name | Nome do usuário |
| persona | Morador / Síndico / Operador / Visitante |
| car_model | Modelo do veículo elétrico |
| battery_kwh | Capacidade da bateria |
| charger_kw | Potência preferida do carregador |
| block | Bloco do condomínio |
| apartment | Apartamento |
| created_at | Data de criação |

**`chats`** (1 usuário → N conversas)
| Campo | Descrição |
|---|---|
| id | Identificador único |
| user_id | Referência ao usuário |
| title | Título da conversa |
| created_at | Data de criação |

**`messages`** (1 conversa → N mensagens)
| Campo | Descrição |
|---|---|
| id | Identificador único |
| chat_id | Referência à conversa |
| role | "user" ou "assistant" |
| content | Texto da mensagem |
| created_at | Data de criação |

---

## 📄 Documentação Adicional (`docs/`)

- **`docs/agents/business_rules.md`**: regras de negócio que o chatbot deve seguir (o que pode e não pode responder, limites por persona, etc.).
- **`docs/agents/context_flow.md`**: detalha o fluxo de construção do contexto enviado à IA.
- **`docs/agents/knowledge_map.md`**: mapa dos temas/conhecimentos que o chatbot domina (carregamento, baterias, condomínio, etc.).
- **`docs/agents/response_patterns.md`**: padrões de formato/tom esperados nas respostas da IA.
- **`docs/agents/system_prompt_spec.md`**: especificação técnica do *system prompt* (estrutura, variáveis, versão).
- **`docs/architecture/system_scope.md`**: escopo geral do sistema, visão de arquitetura atual vs. futura.
- **`docs/database/system_entities.md`**: descrição detalhada das entidades do banco de dados.
- **`docs/modbus/`** e **`docs/meetings/`**: pastas reservadas (vazias) para documentação futura de integração com protocolo Modbus e atas de reunião.

---

## 🤖 Integração com IA

A arquitetura foi projetada para funcionar com múltiplos provedores de IA:

- OpenAI
- Gemini
- Llama
- Ollama
- Outros (via adaptação do `llm_provider.py`)

A camada `ChatService` + `LLMProvider` garante que, no futuro, o modelo de IA possa ser trocado **sem alterar o restante do sistema** — apenas o `llm_provider.py` precisa ser ajustado.

---

## 🎭 Personas e Contexto Inteligente

O chatbot adapta suas respostas conforme a **persona** do usuário logado:

| Persona | Tipo de resposta |
|---|---|
| **Morador** | Foco no uso prático do carregador (como carregar, horários, regras) |
| **Síndico** | Foco em gestão (regras do condomínio, organização de uso) |
| **Operador** | Foco técnico (funcionamento dos equipamentos, diagnósticos) |
| **Visitante** | Informações gerais introdutórias |

Esse contexto é montado a partir de:
- **Dados do usuário**: nome, carro, bateria, carregador.
- **Dados do condomínio**: bloco, apartamento.
- **Persona**: define o "tom" e o foco da resposta.

---

## ✅ Testes Documentados (Sprint 2)

A Sprint 2 exige a execução de **5 casos de teste** (definidos na Sprint 1), cada um registrando:
- Pergunta enviada
- Resposta obtida
- Avaliação: **Adequada / Parcialmente adequada / Inadequada**

> 📌 Esses testes ficam em um **arquivo separado**: `docs/test_cases.md` (não dentro deste README), para manter o README focado na documentação do projeto e o arquivo de testes focado na validação experimental do modelo.

---

---

## 🔮 Visão de longo prazo

Plataforma corporativa de gerenciamento de recarga: backend em microsserviços, integração com
hardware (OCPP, Modbus, MQTT), filas inteligentes, agendamento e dashboards. O núcleo
conversacional desta sprint é a base dessa evolução — trocar modelo, prompt ou política de
memória já é mudança de configuração, não de código.

---

**FIAP × GoodWe · EV Challenge 2026 · Sprint 03**
