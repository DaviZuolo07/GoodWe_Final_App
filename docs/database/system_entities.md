# GoodWe Final App
## System Entities

Versão: 0.1

---

# Objetivo

Este documento define todas as entidades existentes no ecossistema GoodWe Final App.

As entidades aqui descritas representam os objetos do domínio de negócio do sistema.

Este documento NÃO representa tabelas SQL.

Este documento NÃO representa implementação.

Ele representa o modelo conceitual do sistema.

---

# 1. User

Representa qualquer pessoa que utiliza a plataforma.

## Campos

id
name
email
password_hash
role
apartment
created_at
updated_at

## Relacionamentos

User → Vehicle
User → ChargingSession
User → QueueEntry

---

# 2. Role

Representa o perfil operacional do usuário.

## Tipos

resident
visitor
manager
operator
admin

## Responsabilidade

Determinar permissões e visibilidade de informações.

---

# 3. Vehicle

Representa um veículo elétrico.

## Campos

id
user_id

brand
model
year

battery_capacity_kwh

max_ac_power_kw

max_dc_power_kw

connector_type

plate

created_at

## Exemplos

BYD Dolphin
BYD Seal
Volvo EX30
GWM Ora

---

# 4. Charger

Representa um carregador físico.

## Campos

id

name

serial_number

model_id

status

location

connector_type

max_power_kw

is_available

created_at

## Status

available

charging

reserved

offline

fault

maintenance

---

# 5. ChargerModel

Representa o modelo comercial do carregador.

## Campos

id

manufacturer

model_name

max_power_kw

connector_type

phase_type

communication_protocol

## Exemplos

GoodWe AC7
GoodWe AC22
GoodWe Comercial

---

# 6. ChargingSession

Representa uma sessão de carregamento.

## Campos

id

user_id

vehicle_id

charger_id

start_time

end_time

status

battery_start_percent

battery_current_percent

battery_target_percent

energy_delivered_kwh

estimated_finish_time

total_cost

## Status

active

paused

finished

cancelled

---

# 7. QueueEntry

Representa uma posição na fila.

## Campos

id

user_id

vehicle_id

position

requested_at

estimated_start_time

status

## Status

waiting

called

cancelled

finished

---

# 8. Reservation

Representa uma reserva futura de carregamento.

## Campos

id

user_id

charger_id

start_time

end_time

status

---

# 9. ChargerTelemetry

Representa dados operacionais recebidos dos carregadores.

## Campos

id

charger_id

timestamp

power_kw

current_a

voltage_v

energy_total_kwh

temperature

status

fault_code

alarm_code

---

# 10. Alarm

Representa eventos operacionais.

## Campos

id

charger_id

severity

message

created_at

resolved_at

status

## Severidade

info

warning

critical

---

# 11. Notification

Representa notificações para usuários.

## Campos

id

user_id

title

message

created_at

read_at

status

---

# 12. Condominium

Representa o ambiente operacional.

## Campos

id

name

address

total_units

total_chargers

created_at

---

# 13. AIConversation

Representa uma conversa com o ChargeOps AI Assistant.

## Campos

id

user_id

started_at

ended_at

agent_name

---

# 14. AIMessage

Representa uma mensagem da conversa.

## Campos

id

conversation_id

role

content

created_at

## Roles

system

user

assistant

---

# Entidades MVP Sprint 2

Serão utilizadas imediatamente:

User

Vehicle

Charger

ChargingSession

QueueEntry

AIConversation

AIMessage

---

# Entidades Preparadas Para Futuro

Reservation

Alarm

Notification

Condominium

ChargerTelemetry

ChargerModel

---

# Integrações Futuras

Modbus

ChargerTelemetry

Alarm

Charger

---

OCPP

ChargingSession

Charger

User

---

IA

AIConversation

AIMessage

Vehicle

ChargingSession

QueueEntry

Charger