# Fase 2 — Base de conhecimento e eval set · 14 e 15/10

> Cole este arquivo inteiro como primeira mensagem numa sessão de Claude Code aberta na
> raiz do repositório. O `CLAUDE.md` já carrega sozinho.
>
> **Esta é a fase para delegar.** Os 3 PDFs e as perguntas de avaliação são redação, não
> código: qualquer um do grupo faz, e são ~2 dias dos seus 14. Se alguém assumir, você
> pula direto para a Fase 3 e só volta aqui para rodar o `--reindexar`.

## Objetivo

Fechar as quatro categorias de documento que o §5 do enunciado pede. Hoje a base tem
**só uma** (`manual`, 3 PDFs, 76 páginas). Sem variedade de categoria não há como
demonstrar filtro por metadado nem recusa por ausência de contexto — isso custa pontos
nos blocos A e B.

O pipeline da Fase 1 já funciona contra os 3 manuais. Aqui a coleção cresce; o código não
muda. Ao fim, um `python -m src.rag.vector_store --reindexar` e pronto.

## Regras da pasta (já escritas em `data/knowledge_base/README.md`)

- PDF com **texto selecionável**. O `PyMuPDFLoader` não lê PDF escaneado. Teste: dá para
  copiar o texto? Serve.
- Nome no padrão `<tipo>__<descricao-curta>.pdf`, com `tipo` ∈ `manual`, `norma`,
  `regimento`, `faq`, `tarifa`. **O prefixo vira o metadado `categoria` no ChromaDB** — um
  nome fora do padrão quebra o filtro.
- Uma linha no registro de origem **no mesmo commit** do PDF. PDF sem linha na tabela é
  PDF que ninguém sabe de onde veio.
- Documento elaborado pelo grupo é aceito, **desde que declarado** em três lugares: no
  próprio PDF, no registro de origem e no relatório.
- Norma paga (ABNT/IEC) não entra em repositório público. Pode ser citada por documento
  que a referencia (lei, portaria, manual), nunca copiada.

## Entregáveis — prioridade 1 (fazem a sprint andar)

Os três são **escritos pelo grupo** e não dependem de nenhum download. Em um dia de
trabalho fecham as quatro categorias.

**`regimento__condominio-modelo-recarga.pdf`**
Regimento modelo de recarga compartilhada, ancorado na Lei SP 18.403/2026 e na IT-41.
Cubra: direito de instalar ponto na vaga, rateio de consumo, horários, responsabilidade
por dano, uso de vaga compartilhada, procedimento de autorização pelo síndico.
Capa com a declaração: *"Documento elaborado pelo grupo para fins acadêmicos. Não é
regimento de condomínio real."*

**`faq__recarga-condominio.pdf`**
20–30 perguntas e respostas, **derivadas do manual do HCA G2 e do resumo Modbus que já
estão na base** — não invente resposta. Perguntas de morador, síndico e operador: como
iniciar recarga pelo app, o que significa cada código de falha, como agendar, o que fazer
quando o carregador não liga, limites de potência. Mesma declaração de origem na capa.

**`tarifa__condominio-demonstracao.pdf`**
Tabela tarifária do condomínio de demonstração, partindo do R$ 2,10/kWh que já está em
`prompts/base_produtos.json`. Inclua bandeira, horário de ponta/fora de ponta e exemplo de
cálculo de uma sessão. Mesma declaração.

## Entregáveis — prioridade 2 e 3 (melhoram, não bloqueiam)

| Prioridade | Documento | Onde buscar | Nome |
|---|---|---|---|
| 2 | Lei Estadual SP 18.403, de 18/02/2026 | Assembleia Legislativa de SP | `norma__lei-sp-18403-2026-recarga-condominio.pdf` |
| 2 | Tabela de tarifas Enel SP 2026 | site da Enel SP ou ANEEL | `tarifa__enel-sp-2026.pdf` |
| 3 | Portaria CBPMESP 003/970/2026 (IT-41) | Corpo de Bombeiros de SP | `norma__cbpmesp-it41-recarga-garagem.pdf` |
| 3 | ANEEL REN 1.000/2021 — **só o trecho** de recarga de VE | biblioteca da ANEEL | `norma__aneel-ren-1000-2021-recarga-ve.pdf` |
| 3 | Manual do app SolarGo | central de downloads GoodWe | `manual__goodwe-app-solargo.pdf` |

A REN 1.000 inteira é longa e poluiria a busca — extraia só o trecho pertinente e declare
o recorte no registro de origem.

## Decisão já tomada

**`EV_Challenge_2026.pdf` não entra na base.** É o enunciado, não conhecimento de domínio:
poluiria a busca e convidaria o chatbot a responder sobre a própria sprint. O README
deixava em aberto; está fechado.

Também não servem: `1CC - EV CHALLENGE GOODWEFIAP 2026.pdf` (14 páginas só de imagem) e a
apresentação do Challenge (5 páginas só de imagem).

## Segundo entregável — o eval set

O bloco C precisa de **no mínimo 5 pares (pergunta, resposta esperada)** sobre os
documentos. Quem escreveu os PDFs é quem melhor escreve as perguntas. Monte
`evals/eval_set_rag.json` com 8–10 casos, cobrindo:

- 3 perguntas com resposta direta num único documento (fácil)
- 2 perguntas que exigem juntar dois documentos (manual + regimento, por exemplo)
- 2 perguntas de categoria diferente (uma de tarifa, uma de norma)
- **2 perguntas cuja resposta NÃO está na base** — o caso de recusa, que o bloco B cobra
- 1 pergunta com texto de prompt injection embutido

Cada caso: `id`, `categoria`, `pergunta`, `resposta_esperada`, `documento_esperado`,
`pagina_esperada`, `deve_recusar` (bool). Siga o formato de `evals/eval_set.json`, que já
tem uma estrutura boa.

## Critérios de aceite

- [ ] As 4 categorias do §5 existem em `data/knowledge_base/`
- [ ] Todo PDF tem texto selecionável e carrega no `PyMuPDFLoader` sem página vazia
- [ ] Todo PDF tem linha preenchida no registro de origem do README
- [ ] Todo documento escrito pelo grupo está declarado como tal em 3 lugares
- [ ] `evals/eval_set_rag.json` com ≥8 casos, incluindo 2 de recusa e 1 de injection
- [ ] Entrada no `docs/CHANGELOG_SPRINT4.md`

## Gate — fechar a fase

```bat
python -m src.rag.vector_store --reindexar
```

A saída tem que reportar as **4 categorias** com contagem de chunks em cada. Depois teste
na mão uma pergunta de cada categoria nova — uma de tarifa e uma de regimento — e confirme
que a citação aponta para o documento certo.

```bat
python -m pytest tests -q
git add -A
git commit -m "Fase 2: base de conhecimento nas 4 categorias + eval set"
git push origin develop
```

Cole no changelog a saída do `--reindexar`: ela é a prova de "base de conhecimento
expandida" do bloco A, e vai direto para o relatório.
