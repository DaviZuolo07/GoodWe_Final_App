# Base de conhecimento (Sprint 04, §5)

Os PDFs desta pasta são indexados no ChromaDB. O chatbot só pode responder o
que estiver aqui (grounding), e toda resposta cita o documento e a página.

## O que o professor pede (§5)

1. **Manuais de produto GoodWe** (ChargeGrid / EV ChargeOps): datasheets e manuais
   de carregadores, especificações técnicas.
2. **Regimentos condominiais** de carregamento compartilhado.
3. **FAQs de carregamento**.
4. **Tabelas tarifárias**.

## Regras para cada arquivo

- **PDF com texto selecionável.** O `PyMuPDFLoader` não lê PDF escaneado
  (Aula 06, slide 19). Teste: se dá para copiar o texto, serve.
- **Fonte real sempre que possível** (site da GoodWe, material do Challenge,
  distribuidora de energia, ANEEL). O contrato proíbe inventar especificação.
- **Documento escrito pelo grupo** (ex.: regimento modelo, FAQ) é aceito, mas
  precisa ser declarado como tal no relatório e nos metadados. Escreva em
  Word/Docs e exporte para PDF.
- De preferência 5+ páginas por documento, em português quando houver.

## Nome dos arquivos

    <tipo>__<descricao-curta>.pdf

`tipo` é um de: `manual`, `regimento`, `faq`, `tarifa`. Exemplos:

    manual__goodwe-carregador-ac.pdf
    regimento__condominio-modelo-recarga.pdf
    faq__recarga-condominio.pdf
    tarifa__distribuidora-sp-2026.pdf

O prefixo vira metadado de categoria no ChromaDB (filtro por metadado, Aula 05).

## Registro de origem (preencher ao adicionar cada arquivo)

| Arquivo | Origem (URL ou "elaborado pelo grupo") | Data de acesso | Quem adicionou |
|---|---|---|---|
| | | | |
