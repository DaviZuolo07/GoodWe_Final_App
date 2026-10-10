# FAQ — Recarga de veículo elétrico no condomínio (carregador GoodWe HCA G2)

**Documento elaborado pelo grupo do projeto GoodWe ChargeOps (EV Challenge FIAP × GoodWe 2026), outubro de 2026.** Não é publicação da GoodWe. Todas as informações técnicas sobre o carregador foram retiradas do Manual do Usuário GoodWe Série HCA G2 (V1.5-2025-11-11) e do Datasheet da Linha HCA G2. A página do manual de origem está indicada em cada resposta. Regras de uso da vaga e valores cobrados estão no Regimento de Recarga e na Tabela Tarifária do condomínio de demonstração.

## 1. Luzes e estado do carregador

**O que significa cada cor da luz indicadora (LED) do carregador HCA G2?**
Luz verde acesa: o carregador está em modo de espera. Luz verde piscando: o sistema do carregador está sendo atualizado. Luz azul acesa: o carregador está carregando. Luz vermelha acesa: ocorreu uma falha. (Manual HCA G2, seção 3.6.3 e 8.1.)

**A luz vermelha acendeu por 2 segundos quando encostei o cartão RFID. O que aconteceu?**
Significa que o cartão foi encostado antes de o plugue de carregamento ser conectado ao veículo. A sequência correta é: primeiro conecte o plugue no veículo elétrico e só depois encoste o cartão. (Manual HCA G2, seções 3.6.3 e 7.3.4.)

**A luz vermelha piscou duas vezes quando encostei o cartão RFID. O que aconteceu?**
Significa que o carregador e o cartão não correspondem: o cartão não está vinculado àquele carregador. Peça à administração do condomínio a vinculação do seu cartão. (Manual HCA G2, seção 3.6.3.)

**A luz vermelha ficou acesa e a recarga não começa. O que faço?**
Luz vermelha acesa indica falha. O manual orienta consultar o aplicativo SEMS Portal para a solução de problemas detalhada e, se as orientações não resolverem, contatar o serviço pós-venda. No condomínio, avise a administração, que aciona o suporte. Não abra o carregador. (Manual HCA G2, seção 9.5.)

## 2. Como iniciar a recarga

**Quais são as formas de iniciar a recarga no HCA G2?**
Pelo aplicativo (SolarGo ou SEMS Portal), por cartão RFID ou pelo início automático (AUTO Start), que começa a recarga assim que o plugue é conectado. (Datasheet HCA G2, "Método de partida"; Manual HCA G2, seção 7.3.)

**Como iniciar a recarga com o cartão RFID?**
O cartão precisa ter sido vinculado ao carregador com antecedência. Conecte o plugue de carregamento no veículo e, em seguida, encoste o cartão no carregador. Depois de encostar o cartão, o carregador inicia a recarga. (Manual HCA G2, seção 7.3.4.)

**O que é o modo de início automático (AUTO Start)?**
Com o modo de partida automática ativado, o carro começa a carregar assim que o plugue é conectado, sem precisar passar o cartão RFID, desde que não haja um carregamento programado definido. No condomínio de demonstração o início automático fica desligado nas vagas compartilhadas, para que toda sessão seja identificada por cartão. (Manual HCA G2, seção 7.3.3.)

**Como agendar uma recarga?**
O manual do HCA G2 prevê o agendamento de carregamento (Scheduled Charging) pelos aplicativos SolarGo ou SEMS Portal (seção 7.3.2). No condomínio de demonstração, as vagas compartilhadas são reservadas pela administração, conforme o Regimento de Recarga.

## 3. Potência e tempo de recarga

**Por que meu carro carrega abaixo da potência nominal do carregador?**
A potência máxima de carregamento é limitada pela potência máxima do carregador interno do veículo (OBC). Mesmo num carregador de 22 kW, o carro só recebe a potência que o seu carregador de bordo aceita. (Manual HCA G2, seção 3.5.)

**Meu carro só aceita recarga monofásica. Quanto ele recebe num carregador trifásico?**
Quando um carregador trifásico carrega um veículo que só aceita carregamento monofásico, a potência máxima é 1/3 da potência nominal do carregador. Se o veículo só aceita carregamento bifásico, a potência máxima é 2/3 da nominal. (Manual HCA G2, seção 3.5.)

**Qual a potência mínima de recarga?**
A corrente mínima de partida por fase é de 6 A. A potência mínima é de 1,4 kW em carregamento monofásico e de 4,2 kW em carregamento trifásico. (Manual HCA G2, seção 3.5.)

**Quais modos de carregamento o HCA G2 oferece?**
Rápido (usa a rede, com a potência nominal por padrão), Prioridade de energia fotovoltaica (só o excedente solar carrega o veículo) e Energia fotovoltaica + bateria. Nos modos com prioridade fotovoltaica, a potência de recarga é limitada pela potência máxima de saída do inversor. (Manual HCA G2, seção 3.3.)

**O que é o controle dinâmico de carga?**
Com o controle dinâmico de carga ativado, o carregador ajusta a velocidade de recarga, ou até pausa a recarga, com base nos dados do medidor e na corrente de conexão à rede definida, para evitar o disparo do fusível principal. Ele reinicia sozinho quando a folga de corrente volta a permitir. Por isso, em horário de pico do prédio, a recarga pode ficar mais lenta ou pausar. (Manual HCA G2, seção 3.5.)

## 4. Uso seguro

**O carregador pode ficar em garagem aberta, exposto a chuva?**
O carregador tem grau de proteção IP66 e o plugue de carregamento, IP55, com recursos antipoeira e à prova d'água, e pode ser operado em áreas externas. (Manual HCA G2, seção 3.5; Datasheet HCA G2.)

**Posso usar extensão ou adaptador no cabo de recarga?**
Não. O manual proíbe estender o cabo de carregamento, porque isso reduz a proteção e cria risco de choque elétrico. O carregador também só pode ser usado para carregar veículos elétricos, nenhum outro aparelho. (Manual HCA G2, seção 2.2.)

**O que fazer com o cabo depois de usar?**
Cubra o plugue de carregamento e enrole o cabo ao redor do carregador. O cabo não deve ser dobrado, espremido ou emaranhado. (Manual HCA G2, seção 2.2.)

**Quem pode instalar, consertar ou mexer na parte elétrica do carregador?**
Somente profissionais qualificados ou pessoal treinado podem instalar, operar a manutenção e substituir o equipamento ou peças. Morador não deve abrir o carregador nem o quadro de proteção. (Manual HCA G2, seção 2.3.)

**O carregador tem botão de emergência?**
Sim, o HCA G2 tem desligamento de emergência integrado (botão de parada de emergência). Se a falha "Parada de emergência" aparecer, é porque o botão está pressionado; a solução indicada é soltar o botão. (Datasheet HCA G2; Manual HCA G2, seção 9.5.)

## 5. Falhas comuns

**Apareceu "tempo limite de preparação". O que fazer?**
A causa é a comunicação do sinal CP que não foi bem-sucedida. Verifique se o veículo já está totalmente carregado e reconecte o conector depois de deixá-lo desconectado por cerca de 15 segundos. Se persistir, contate a administração para acionar o pós-venda. (Manual HCA G2, seção 9.5, falha 9.)

**A recarga parou sozinha no inverno. Por quê?**
Uma das causas da falha "tempo limite de desvio" é a temperatura ambiente muito baixa, que impede a bateria de carregar. O manual recomenda iniciar o pré-aquecimento do veículo cerca de cinco minutos antes da recarga em ambiente muito frio. (Manual HCA G2, seção 9.5, falha 8.)

**O carregador desligou por temperatura. É defeito?**
A falha de temperatura ambiente ocorre quando a temperatura do carregador passa de 98 graus. O problema é removido após o resfriamento e o carregador volta ao modo de espera. (Manual HCA G2, seção 9.5, falha 4.)

## 6. Manutenção

**Com que frequência o carregador passa por manutenção?**
O manual define: teste do botão de parada de emergência uma vez a cada 6 meses; verificação das conexões elétricas e da vedação de terminais e portas uma vez a cada 6 a 12 meses. No condomínio, a manutenção é feita por empresa contratada pela administração. (Manual HCA G2, seção 9.4.)

## 7. Custos e regras

**Quanto custa recarregar no condomínio?**
O valor por kWh e a forma de cobrança estão na Tabela Tarifária de Recarga do condomínio de demonstração. As regras de reserva, tempo de uso e penalidades estão no Regimento de Recarga.
