# GoodWe Final App
## System Scope

Versão: 0.1
Status: Foundation Draft

---

# 1. Visão Geral

O GoodWe Final App é uma plataforma operacional inteligente para gerenciamento de carregamento de veículos elétricos em ambientes comerciais.

O foco principal do projeto é resolver o desafio proposto pela GoodWe:

Migrar a gestão de carregamento do ambiente residencial para o ambiente comercial.

A solução escolhida pela equipe é direcionada para:

CONDOMÍNIOS

A plataforma funcionará como um centro operacional de monitoramento, orquestração e suporte para recarga de veículos elétricos.

---

# 2. Objetivo Principal

Permitir que moradores, visitantes, síndicos, operadores e administradores possam utilizar e gerenciar uma infraestrutura compartilhada de carregadores GoodWe de forma organizada, inteligente e eficiente.

---

# 3. Problemas Que a Plataforma Resolve

## Utilização compartilhada

Em condomínios existe um número limitado de carregadores.

A plataforma deve organizar o uso dos carregadores.

---

## Filas de carregamento

Usuários precisam saber:

- posição na fila
- previsão de início
- previsão de término

---

## Visibilidade operacional

Os usuários precisam visualizar:

- carregadores disponíveis
- carregadores ocupados
- carregadores com falha
- sessões em andamento

---

## Falta de informações

Os usuários precisam saber:

- potência atual
- energia entregue
- tempo restante
- custo estimado
- histórico de carregamentos

---

## Apoio operacional

A plataforma deve possuir um assistente de IA para auxiliar usuários e operadores.

---

# 4. Perfis de Usuário

## Morador

Responsável por utilizar a infraestrutura de carregamento.

Necessidades:

- visualizar sessões
- visualizar carregadores
- entrar em filas
- acompanhar carregamento
- consultar histórico
- obter suporte via IA

---

## Visitante

Usuário temporário.

Necessidades:

- solicitar acesso
- registrar veículo
- utilizar carregadores autorizados
- consultar disponibilidade

---

## Síndico

Responsável pela administração do condomínio.

Necessidades:

- visualizar utilização geral
- acompanhar indicadores
- analisar ocupação
- acompanhar consumo energético

---

## Operador

Responsável pela operação da infraestrutura.

Necessidades:

- monitorar carregadores
- monitorar falhas
- acompanhar telemetria
- visualizar eventos operacionais

---

## Administrador

Perfil com acesso total.

Necessidades:

- gestão completa da plataforma
- gestão de usuários
- gestão de carregadores
- gestão de permissões
- gestão operacional

---

# 5. Módulos do Sistema

## Módulo de Autenticação

Responsável por:

- login
- logout
- permissões
- controle de acesso

---

## Módulo de Usuários

Responsável por:

- cadastro
- edição
- permissões
- perfil

---

## Módulo de Veículos

Responsável por:

- cadastro de veículos
- informações técnicas
- compatibilidade de carregamento

---

## Módulo de Carregadores

Responsável por:

- monitoramento
- status
- disponibilidade
- potência

---

## Módulo de Sessões

Responsável por:

- iniciar carregamento
- encerrar carregamento
- acompanhar progresso

---

## Módulo de Filas

Responsável por:

- gerenciamento de espera
- ordenação
- previsão de atendimento

---

## Módulo de Telemetria

Responsável por:

- dados operacionais
- consumo energético
- potência
- corrente
- tensão
- temperatura

---

## Módulo de IA

ChargeOps AI Assistant.

Responsável por:

- suporte operacional
- dúvidas técnicas
- explicação de dados
- interpretação operacional
- apoio aos usuários

---

# 6. Dados Operacionais Monitorados

A plataforma deverá monitorar:

- carregadores
- sessões
- filas
- veículos
- usuários
- consumo energético
- potência
- corrente
- tensão
- disponibilidade
- alarmes
- falhas

---

# 7. Integrações Futuras

## Modbus

Dados futuros:

- status do carregador
- potência
- corrente
- tensão
- energia acumulada
- alarmes
- falhas

---

## OCPP

Dados futuros:

- sessões
- autenticação
- eventos
- telemetria

---

## Carregadores GoodWe

Integração futura com equipamentos reais.

---

# 8. Escopo da IA

O ChargeOps AI Assistant deverá ser capaz de:

- explicar conceitos técnicos
- responder dúvidas operacionais
- interpretar dados de carregamento
- auxiliar usuários
- auxiliar operadores
- auxiliar administradores

---

# 9. Conhecimento da IA

A IA deverá possuir conhecimento sobre:

- veículos elétricos
- carregadores GoodWe
- carregamento AC
- carregamento DC
- potência
- energia
- eficiência energética
- telemetria
- filas
- operação de condomínios
- OCPP
- Modbus

---

# 10. Dados Que a IA Utilizará

## Conhecimento

Informações presentes em:

- system prompt
- contexto GoodWe
- regras operacionais

---

## Dados Operacionais

Informações provenientes de:

- banco de dados
- sessões
- filas
- carregadores
- telemetria
- integrações futuras

---

# 11. Fora do Escopo Atual

Nesta fase não serão implementados:

- multiagentes
- integração real Modbus
- integração real OCPP
- integração real com carregadores
- aplicativo mobile

A arquitetura deverá permanecer preparada para evolução futura.

---

# 12. Objetivo da Sprint 2

Implementar a primeira versão do ChargeOps AI Assistant.

Requisitos:

- GPT-OSS 120B via Ollama
- memória conversacional
- contexto GoodWe
- interface Streamlit
- histórico de mensagens
- testes documentados
- README completo

Esta implementação será reutilizada futuramente dentro da plataforma GoodWe Final App.