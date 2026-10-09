# Base de conhecimento (Sprint 04, §5)

Os PDFs desta pasta são indexados no ChromaDB. O chatbot só pode responder o
que estiver aqui (grounding), e toda resposta cita o documento e a página.

## Regras para cada arquivo

- **PDF com texto selecionável.** O `PyMuPDFLoader` não lê PDF escaneado
  (Aula 06). Teste: se dá para copiar o texto, serve.
- **Fonte real sempre que possível.** O enunciado proíbe inventar especificação.
- **Documento escrito ou derivado pelo grupo** é aceito, mas precisa ser
  declarado como tal aqui, no próprio PDF e no relatório.
- **Norma paga (ABNT/IEC) não entra no repositório público.** Pode ser citada
  por documentos que a referenciam (lei, portaria, manual), nunca copiada.

## Nome dos arquivos

    <tipo>__<descricao-curta>.pdf

`tipo` é um de: `manual`, `norma`, `regimento`, `faq`, `tarifa`. O prefixo vira
o metadado `categoria` no ChromaDB (filtro por metadado, Aula 05).

| tipo | o que é |
|---|---|
| `manual` | documentação de produto GoodWe (manual, datasheet, protocolo) |
| `norma` | lei, resolução da ANEEL, portaria do Corpo de Bombeiros |
| `regimento` | regras do condomínio para recarga compartilhada |
| `faq` | perguntas e respostas de recarga |
| `tarifa` | tabela tarifária da distribuidora ou do condomínio |

## Registro de origem

| Arquivo | Págs. | Origem | Tipo de fonte | Acesso | Quem |
|---|---|---|---|---|---|
| `manual__goodwe-hca-g2-manual-usuario.pdf` | 70 | Manual do Usuário GoodWe HCA G2 (PT), material do EV Challenge fornecido pela GoodWe | oficial, sem alteração | 06/10/2026 | Davi |
| `manual__goodwe-hca-g2-datasheet.pdf` | 2 | Datasheet GoodWe HCA G2 (PT), material do EV Challenge fornecido pela GoodWe | oficial, sem alteração | 06/10/2026 | Davi |
| `manual__goodwe-hca-g2-modbus-resumo.pdf` | 4 | Resumo em português do "Mapa MODBUS_HCA G2" (protocolo V1.0.15, 12/09/2025), fornecido pela GoodWe ao Challenge | **derivado pelo grupo** (filtrado e traduzido) | 06/10/2026 | Davi |

### Sobre o resumo do Modbus

O original tem 9 páginas em chinês e inglês, em formato de planilha. Entrou
na base só o que serve a morador, síndico e operador: falhas e alarmes, estado
do carregador, medições, sessão de recarga, agendamento, modos e limites de
potência, cartões RFID. Saíram: histórico de versões, texto em chinês,
registradores reservados, versões internas de software/hardware, ajuste de
relógio e envio de firmware. Nenhum valor foi alterado ou acrescentado. Os
códigos de alarme IoT (30000–30015) e de motivo de encerramento (10168)
dependem de apêndices que não temos; o PDF diz isso explicitamente para o
chatbot recusar em vez de inventar.

## A coletar (F1 em aberto)

Baixar o PDF oficial, conferir que o texto é selecionável, salvar aqui com o
nome indicado e preencher a tabela acima. Itens marcados "conferir" não foram
confirmados na fonte oficial.

### Produto GoodWe (`manual__`)

| Documento | Onde buscar | Nome sugerido |
|---|---|---|
| Guia rápido de instalação do HCA G2 (conferir se existe em PT) | Central de downloads da GoodWe Brasil | `manual__goodwe-hca-g2-guia-rapido.pdf` |
| Manual do app SolarGo (o manual do HCA G2 usa o app para iniciar e agendar recarga) | Central de downloads da GoodWe | `manual__goodwe-app-solargo.pdf` |
| Manual do SEMS Portal / SEMS+ (monitoramento) | Central de downloads da GoodWe | `manual__goodwe-sems-portal.pdf` |
| Termo de garantia GoodWe Brasil que cubra carregadores (conferir) | Site da GoodWe Brasil | `manual__goodwe-garantia.pdf` |
| `EV_Challenge_2026.pdf` (29 págs., texto selecionável) | Material do Challenge | decidir se entra: é enunciado, não produto |

Não servem: `1CC - EV CHALLENGE GOODWEFIAP 2026.pdf` (14 páginas só de imagem)
e a apresentação do Challenge (pouco texto, 5 páginas só de imagem).

### Normas e regulação (`norma__`)

| Documento | Onde buscar | Nome sugerido |
|---|---|---|
| Lei Estadual SP 18.403, de 18/02/2026 (direito de instalar ponto de recarga na vaga) | Assembleia Legislativa de SP | `norma__lei-sp-18403-2026-recarga-condominio.pdf` |
| Portaria CBPMESP 003/970/2026, que revisou a Instrução Técnica 41 (recarga em garagens) | Corpo de Bombeiros de SP | `norma__cbpmesp-it41-recarga-garagem.pdf` |
| ANEEL REN 1.000/2021, só o trecho sobre recarga de veículos elétricos (a resolução inteira é longa e poluiria a busca) | Biblioteca da ANEEL | `norma__aneel-ren-1000-2021-recarga-ve.pdf` |

### Tarifas (`tarifa__`)

| Documento | Onde buscar | Nome sugerido |
|---|---|---|
| Resolução homologatória do reajuste 2026 da Enel São Paulo (vigência 04/07/2026; conferir o número) ou a tabela de tarifas da distribuidora | ANEEL / site da Enel SP | `tarifa__enel-sp-2026.pdf` |
| Tarifa de recarga do condomínio de demonstração (hoje R$ 2,10/kWh em `prompts/base_produtos.json`) | elaborado pelo grupo | `tarifa__condominio-demonstracao.pdf` |

### Regimento e FAQ (`regimento__`, `faq__`)

Regimento interno real raramente é público. Caminho proposto: o grupo escreve
um regimento modelo e um FAQ, ancorados na Lei 18.403/2026, na IT-41 e no
manual do HCA G2, e declara os dois como "elaborado pelo grupo".

| Documento | Nome sugerido |
|---|---|
| Regimento modelo de recarga compartilhada | `regimento__condominio-modelo-recarga.pdf` |
| FAQ de recarga em condomínio | `faq__recarga-condominio.pdf` |
