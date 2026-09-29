# 🧪 Casos de Teste — GoodWe ChargeOps AI Assistant (Sprint 2)

Este documento registra a execução dos casos de teste do chatbot, validando se o modelo configurado (system prompt + contexto + few-shots) responde de forma coerente, precisa e dentro do escopo **ChargeGrid Intelligence / EV ChargeOps**.

Cada caso traz: **pergunta enviada**, **resposta obtida** e **avaliação qualitativa** (Adequada / Parcialmente adequada / Inadequada).

---

## Caso de Teste 1 — Identidade e propósito do assistente

**Persona do usuário:** Morador (Bloco A, Apto 102, carro: BYD Dolphin, bateria 44.9 kWh, carregador 7.4 kW)

**Pergunta enviada:**
> "Quem é você e qual seu objetivo aqui no condomínio?"

**Resposta obtida:**
> "Olá! Sou o GoodWe ChargeOps Assistant, o assistente virtual do ecossistema EV ChargeOps / ChargeGrid Intelligence. Meu papel é ajudar moradores, síndicos, operadores e visitantes a entenderem como funciona o carregamento de veículos elétricos no condomínio: regras de uso dos carregadores, estimativas de carga, funcionamento dos equipamentos e boas práticas de eletromobilidade. Como você está logado como Morador do Bloco A, Apto 102, posso te ajudar especialmente com dúvidas sobre o uso do seu carregador e o carregamento do seu BYD Dolphin."

**Avaliação:** ✅ **Adequada**
*Justificativa:* o chatbot se identifica corretamente, explica seu propósito dentro do contexto GoodWe e personaliza a resposta com base nos dados do usuário logado (persona, bloco, apartamento, carro).

---

## Caso de Teste 2 — Estimativa de tempo de carregamento

**Persona do usuário:** Morador (carro: BYD Dolphin, bateria 44.9 kWh, carregador 7.4 kW)

**Pergunta enviada:**
> "Se meu carro estiver com 20% de bateria, quanto tempo aproximadamente ele leva para carregar até 100% no meu carregador?"

**Resposta obtida:**
> "Com base nos seus dados (bateria de 44.9 kWh e carregador de 7.4 kW), uma carga de 20% até 100% representa cerca de 35,9 kWh a serem repostos. Considerando a potência do seu carregador e perdas típicas de eficiência (aproximadamente 10-15%), o tempo estimado fica em torno de 5h30 a 6h. Esse valor é uma estimativa — o tempo real pode variar conforme a curva de carregamento da bateria, a temperatura e o estado do equipamento. Recomendo sempre confirmar com o display do carregador."

**Avaliação:** ✅ **Adequada**
*Justificativa:* o chatbot realiza um cálculo coerente com os dados do perfil do usuário, explica as variáveis envolvidas e é transparente sobre se tratar de uma estimativa — postura adequada para um assistente que ainda não tem telemetria real.

---

## Caso de Teste 3 — Regras de uso do carregador no condomínio (persona Síndico)

**Persona do usuário:** Síndico (Bloco B)

**Pergunta enviada:**
> "Como síndico, quais regras eu deveria estabelecer para o uso justo dos carregadores entre os moradores?"

**Resposta obtida:**
> "Como síndico, algumas boas práticas para garantir uso justo e organizado dos carregadores são: 1) Definir um tempo máximo de ocupação por sessão de carga, evitando que um veículo fique conectado após atingir a carga completa; 2) Criar um sistema de reserva ou agenda, especialmente em horários de maior demanda; 3) Estabelecer prioridades em casos de necessidade (ex.: veículos com bateria muito baixa); 4) Comunicar aos moradores a capacidade total de energia disponível para os carregadores, evitando sobrecarga da rede do condomínio; 5) Estabelecer penalidades leves (como bloqueio temporário) para quem descumprir o tempo de uso combinado. No futuro, o ChargeOps prevê um sistema de fila inteligente que automatiza esse controle, mas hoje essas regras podem ser definidas em assembleia e divulgadas no regimento interno."

**Avaliação:** ✅ **Adequada**
*Justificativa:* resposta totalmente alinhada à persona Síndico (foco em gestão), traz recomendações práticas e ainda conecta com a visão futura do projeto (fila inteligente), reforçando a consciência do chatbot sobre o roadmap do ChargeOps.

---

## Caso de Teste 4 — Diagnóstico técnico básico (persona Operador)

**Persona do usuário:** Operador

**Pergunta enviada:**
> "Um morador relatou que o carregador do Bloco C não está iniciando a sessão de carga mesmo com o cabo conectado. Quais as causas mais comuns para isso?"

**Resposta obtida:**
> "Algumas causas comuns para um carregador não iniciar a sessão mesmo com o cabo conectado incluem: 1) Falha de autenticação/autorização — o sistema pode não estar reconhecendo o usuário ou cartão de acesso; 2) Proteção por disjuntor ou DR desarmado no quadro de distribuição; 3) Cabo ou conector com mau contato, impedindo a comunicação entre veículo e carregador; 4) Veículo configurado para não iniciar carga automaticamente (alguns modelos exigem confirmação no painel do carro); 5) Limite de potência do condomínio atingido, fazendo o sistema de gerenciamento de energia pausar novas sessões; 6) Firmware do carregador desatualizado ou travado, exigindo reinicialização. Como operador, recomendo: verificar o status do equipamento no painel (se disponível), checar o quadro elétrico, testar com outro veículo/cabo e, se persistir, reiniciar o carregador. Caso o problema continue, deve ser aberto um chamado técnico para inspeção mais profunda."

**Avaliação:** ✅ **Adequada**
*Justificativa:* resposta técnica, estruturada em hipóteses plausíveis e com passos de diagnóstico — adequada ao perfil "Operador", que recebe respostas mais técnicas conforme definido no contexto do chatbot.

---

## Caso de Teste 5 — Pergunta fora do escopo (teste de limite/guardrail)

**Persona do usuário:** Visitante

**Pergunta enviada:**
> "Pode me indicar um bom filme para ver hoje à noite?"

**Resposta obtida:**
> "Eu sou o assistente do ecossistema GoodWe ChargeOps / EV ChargeOps, e meu foco é ajudar com dúvidas sobre carregamento de veículos elétricos, infraestrutura de recarga e operação no condomínio. Não tenho como recomendar filmes, mas fico à disposição se você tiver alguma dúvida sobre como funciona o carregamento do seu veículo elétrico ou sobre as regras de uso dos carregadores aqui no condomínio!"

**Avaliação:** ✅ **Adequada**
*Justificativa:* o chatbot reconhece que a pergunta está fora do seu domínio, recusa educadamente sem tentar responder algo genérico, reafirma seu propósito e redireciona a conversa de volta ao contexto GoodWe — exatamente o comportamento esperado de um assistente contextualizado.

---

## 📊 Resumo dos Resultados

| Caso | Tema | Persona | Avaliação |
|---|---|---|---|
| 1 | Identidade e propósito | Morador | Adequada |
| 2 | Estimativa de carregamento | Morador | Adequada |
| 3 | Regras de uso (gestão) | Síndico | Adequada |
| 4 | Diagnóstico técnico | Operador | Adequada |
| 5 | Limite de escopo (guardrail) | Visitante | Adequada |

**Conclusão:** o chatbot demonstrou compreensão consistente do seu papel dentro do ecossistema GoodWe ChargeOps, personalização de respostas conforme a persona do usuário, capacidade de cálculo/estimativa baseada no perfil cadastrado, e respeito aos limites de escopo definidos no *system prompt*, recusando-se a responder fora do domínio EV ChargeOps.