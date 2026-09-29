# GoodWe Final App

## AI Context Flow

Versão: 0.1

---

# Objetivo

Este documento define como informações circulam dentro da arquitetura de Inteligência Artificial do GoodWe Final App.

Seu propósito é garantir:

* previsibilidade
* modularidade
* escalabilidade
* reutilização futura

Toda implementação da camada de IA deverá respeitar este fluxo.

---

# Visão Geral

A IA não recebe apenas uma pergunta.

A IA recebe contexto.

O objetivo da arquitetura é transformar uma simples pergunta em uma resposta contextualizada, consistente e alinhada ao ecossistema GoodWe.

---

# Fluxo Geral

Usuário

↓

Interface

↓

Router

↓

Memória

↓

Contexto GoodWe

↓

System Prompt

↓

Agente

↓

LLM

↓

Resposta

↓

Interface

---

# Etapa 1 — Usuário

Representa qualquer pessoa utilizando o sistema.

Exemplos futuros:

* morador
* visitante
* síndico
* operador
* administrador

Na Sprint 2 todos serão tratados como usuário genérico.

---

# Entrada Recebida

Exemplo:

"Quanto tempo falta para meu carro atingir 80%?"

Esta mensagem sozinha não possui contexto suficiente.

Por isso o restante do fluxo existe.

---

# Etapa 2 — Interface

Responsável por capturar a mensagem.

Na Sprint 2:

Streamlit

Responsabilidades:

* exibir histórico
* enviar mensagens
* receber respostas
* iniciar sessões

A interface não possui inteligência.

Ela apenas transmite informações.

---

# Etapa 3 — Router

Responsável por decidir como a pergunta será processada.

Objetivo:

Evitar uso desnecessário da LLM.

---

# Decisão do Router

O Router deverá classificar perguntas em categorias.

Exemplos:

## Categoria 1

Perguntas conceituais simples

Exemplo:

"O que é Modbus?"

Resposta futura:

Base de conhecimento local.

Sem uso da LLM.

---

## Categoria 2

Perguntas operacionais

Exemplo:

"Qual a diferença entre kW e kWh?"

Poderão ser respondidas localmente.

---

## Categoria 3

Perguntas contextuais

Exemplo:

"Meu carro tem 60 kWh e está em 20%, quanto falta para chegar em 80%?"

Necessitam raciocínio.

Utilizar agente + LLM.

---

## Categoria 4

Interpretação operacional

Exemplo:

"Tenho três carregadores ocupados e cinco veículos aguardando. O que isso significa?"

Necessita interpretação.

Utilizar agente + LLM.

---

# Objetivo Futuro

O Router deverá reduzir chamadas desnecessárias ao modelo.

---

# Etapa 4 — Memória

Responsável por armazenar histórico da conversa.

---

# Estrutura

System

User

Assistant

User

Assistant

...

---

# Objetivo

Permitir continuidade.

Exemplo:

Usuário:

"Meu carro possui 60 kWh."

Pergunta posterior:

"Quanto tempo falta para atingir 80%?"

A IA deverá utilizar o contexto anterior.

---

# Escopo da Sprint 2

Memória apenas em RAM.

Sem:

* vetores
* embeddings
* banco vetorial
* persistência permanente

---

# Etapa 5 — Contexto GoodWe

Representa o conhecimento institucional do projeto.

Origem:

goodwe_context.py

---

# Conteúdo

* Challenge GoodWe
* ChargeOps
* ChargeGrid Intelligence
* condomínios
* eletromobilidade
* carregadores
* telemetria
* infraestrutura

---

# Função

Garantir alinhamento ao domínio do projeto.

---

# Etapa 6 — System Prompt

Representa a identidade do agente.

Origem:

system_prompt.txt

---

# Função

Definir:

* comportamento
* escopo
* limites
* regras
* tom de comunicação

---

# O Prompt Não Deve Conter

* telemetria atual
* usuários atuais
* filas atuais
* dados dinâmicos

---

# Etapa 7 — Agente

Responsável por preparar o contexto final enviado ao modelo.

Na Sprint 2:

ChargeOpsAgent

---

# Responsabilidades

* organizar contexto
* aplicar regras
* aplicar memória
* aplicar contexto GoodWe
* aplicar prompt

---

# Estrutura Conceitual

System Prompt

*

GoodWe Context

*

Conversation Memory

*

User Message

↓

Prompt Final

---

# Etapa 8 — LLM

Modelo responsável pela geração da resposta.

Na Sprint 2:

GPT-OSS 120B

via Ollama

---

# Abstração

A arquitetura deve permitir troca futura para:

* Qwen
* DeepSeek
* Llama
* modelos futuros

Sem alterar o restante do sistema.

---

# Etapa 9 — Resposta

A resposta produzida retorna ao agente.

Antes de chegar ao usuário poderá passar por validações futuras.

---

# Validações Futuras

* controle de permissões
* filtragem por perfil
* auditoria
* observabilidade

---

# Etapa 10 — Interface

A resposta é exibida ao usuário.

A conversa continua.

O ciclo reinicia.

---

# Fluxo Resumido

User Message

↓

Router

↓

Memory

↓

GoodWe Context

↓

System Prompt

↓

ChargeOpsAgent

↓

GPT-OSS

↓

Response

↓

Memory Update

↓

UI

---

# Fluxo Futuro de Personas

Sprint 2

User

↓

ChargeOpsAgent

---

Fase Posterior

User

↓

Persona Detector

↓

ResidentAgent

VisitorAgent

ManagerAgent

OperatorAgent

AdminAgent

↓

Resposta

---

# Fluxo Futuro de Dados Operacionais

Backend

↓

PostgreSQL

↓

Repositories

↓

Services

↓

Agent Context Builder

↓

Agente

↓

LLM

---

# Fluxo Futuro Modbus

Carregador GoodWe

↓

Modbus

↓

Backend

↓

Banco de Dados

↓

Agente

↓

Usuário

---

# Princípio Arquitetural Final

A LLM nunca será a fonte única de verdade.

A LLM será responsável por:

* interpretação
* explicação
* raciocínio

Os dados operacionais deverão vir do sistema.

---

# Objetivo Final

Garantir que o ChargeOps AI Assistant opere sempre baseado em contexto, memória, regras de negócio e conhecimento institucional, permitindo evolução contínua para múltiplos agentes, integração com dados reais e crescimento da plataforma GoodWe Final App sem necessidade de reestruturação arquitetural.
