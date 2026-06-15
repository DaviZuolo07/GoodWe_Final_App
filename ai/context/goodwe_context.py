"""
GoodWe ChargeOps Context

Contexto operacional fixo utilizado pelo chatbot.

Não contém regras de comportamento.
Não contém persona.
Não contém memória.

Contém apenas conhecimento institucional e operacional
do domínio GoodWe ChargeOps.
"""


GOODWE_CONTEXT = """
# GOODWE CHARGEOPS

Você está operando dentro do ecossistema GoodWe ChargeOps.

O GoodWe ChargeOps é uma plataforma voltada para gerenciamento
inteligente de carregamento de veículos elétricos em condomínios.

O objetivo da plataforma é transformar carregadores de veículos
elétricos em uma infraestrutura comercial compartilhada,
permitindo melhor utilização dos recursos disponíveis.

## PRINCIPAIS FUNCIONALIDADES

- Monitoramento de carregadores
- Gerenciamento de filas
- Controle de sessões de carregamento
- Visualização operacional
- Monitoramento energético
- Dados de telemetria
- Gestão de veículos
- Gestão de usuários
- Suporte operacional via IA

## TIPOS DE USUÁRIOS

A plataforma será utilizada futuramente por:

- Moradores
- Visitantes
- Operadores
- Síndicos
- Administradores

Nesta Sprint 2 todas as personas utilizam o mesmo agente.

## CONCEITOS IMPORTANTES

Carregador:
Equipamento responsável por fornecer energia ao veículo.

Sessão de carregamento:
Período entre início e término da recarga.

Fila:
Lista de usuários aguardando utilização de um carregador.

Potência:
Velocidade de transferência de energia para o veículo.

Energia:
Quantidade total de energia entregue ao veículo.

Estado do carregador:
Disponível, ocupado, reservado, offline ou em falha.

## INTEGRAÇÕES FUTURAS

A arquitetura será preparada para receber dados reais de:

- Modbus
- OCPP
- Telemetria GoodWe
- Banco de dados operacional

## DADOS FUTUROS DISPONÍVEIS AO AGENTE

Futuramente o agente poderá consultar:

- nível de bateria
- potência atual
- corrente
- tensão
- energia acumulada
- carregador utilizado
- posição na fila
- tempo restante
- status da sessão
- falhas e alarmes

Caso esses dados não estejam disponíveis,
deixe claro que a informação ainda não foi fornecida.
"""