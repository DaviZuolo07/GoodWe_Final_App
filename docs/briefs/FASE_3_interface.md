# Fase 3 — Interface Gradio · 16 e 17/10

> Cole este arquivo inteiro como primeira mensagem numa sessão de Claude Code aberta na
> raiz do repositório. O `CLAUDE.md` já carrega sozinho.
>
> Chega aqui com o `chain_rag` pronto e a base nas 4 categorias. É a fase mais rápida de
> todas e a mais visível — bom momento depois de 5 dias de pipeline.

## Objetivo

Interface web em Gradio consumindo o RAG, **com citação visível**. Aula 08 + §3 item 5.
Parte do bloco A (35 pts).

## Ordem de construção — dois dias, nessa ordem

**Dia 1: a tela mínima que vale ponto.** `gr.ChatInterface` + o painel de fontes. Sem
streaming, sem memória, sem botão de limpar. Se a sprint atrasar e esta fase for
comprimida, é isto que precisa existir — a rubrica pede "interface funcional com citação
visível", nada além.

**Dia 2: o resto.** Streaming com `yield`, memória por sessão, botão de limpar, tratamento
de erro. Tudo isso é experiência, não ponto, e está na lista de corte do roadmap.

## Entregáveis em `app/`

**`main.py`** — a interface.

Base da Aula 08, com `gr.Blocks` + `gr.ChatInterface`:

```python
import uuid, gradio as gr

with gr.Blocks(title="GoodWe ChargeOps") as demo:
    sid = gr.State(lambda: str(uuid.uuid4()))
    gr.Markdown("## ⚡ GoodWe ChargeOps — assistente de recarga em condomínio")
    gr.ChatInterface(
        fn=chat,
        type="messages",
        additional_inputs=[sid],
        examples=[...],   # 3 perguntas reais do domínio
    )

demo.launch()
```

Pontos obrigatórios:

- **`type="messages"`** — formato `[{role, content}]`, o mesmo do `RunnableWithMessageHistory`.
- **Streaming com `yield`.** Acumule parcial e dê `yield` a cada chunk de
  `chain.stream(...)`. Sem isso o usuário encara 15 s de tela parada.
- **Primeiro `yield` é `"⏳ Buscando nos documentos..."`** — o retrieval tem latência e o
  usuário precisa saber que o app está trabalhando.
- **Memória por sessão.** `gr.State(lambda: str(uuid.uuid4()))` gera um id por aba;
  `RunnableWithMessageHistory` usa esse id como chave. Dois usuários simultâneos não
  podem ver o histórico um do outro.
- **Botão de limpar sessão** que zera `store[session_id]`. Histórico crescente degrada a
  qualidade.
- **`try/except` em volta do `stream`**, fazendo `yield` de mensagem de erro legível. O
  Ollama Cloud tem latência variável e às vezes cai — o app não pode travar.
- `gr.Textbox(max_lines=5)` ou truncamento, para não estourar tokens.

**A citação visível — é isto que vale ponto**

Não basta a citação sair no texto da resposta. O enunciado pede "interface funcional com
**citação visível**". Faça um painel lateral ou um accordion abaixo da resposta mostrando,
para cada chunk recuperado:

- nome do documento e página (`page + 1`)
- a `categoria` (vinda do metadado)
- o score de similaridade (`1 - distancia`, do `similarity_search_with_score`)
- o trecho do texto recuperado

Um `gr.Accordion("📄 Fontes consultadas", open=False)` com um `gr.Markdown` dentro resolve
e fica limpo. O avaliador tem que **ver** de onde veio a resposta sem ler o código.

Quando o bot recusar ("Não encontrei essa informação nos documentos fornecidos"), o painel
deve dizer que nada passou do limiar de relevância — isso demonstra o grounding na tela.

**`app/README.md`** — como executar. Exigido pelo §5.
- `pip install -r requirements.txt`
- copiar `.env.example` para `.env` e colar a chave
- `python -m src.rag.vector_store --reindexar` (uma vez)
- `python app/main.py`
- print da tela funcionando

## Segurança

- A chave vem de `os.getenv("OLLAMA_API_KEY")` via `python-dotenv`. **Nunca** apareça na
  interface, em label, em placeholder ou em mensagem de erro.
- `share=True` gera URL pública. Útil para a demo, mas qualquer pessoa com o link usa a
  sua chave. Deixe `share=False` por padrão e documente a flag no README.

## Critérios de aceite

- [ ] `python app/main.py` sobe a interface
- [ ] Resposta aparece token a token, com mensagem de carregamento antes
- [ ] Painel de fontes mostra documento, página, categoria, score e trecho
- [ ] Pergunta fora da base mostra a recusa **e** o painel indicando que nada passou do limiar
- [ ] Duas abas do browser não compartilham histórico
- [ ] Botão de limpar sessão funciona
- [ ] Queda do Ollama vira mensagem legível, não traceback na tela
- [ ] `app/README.md` com o passo a passo e um print

## Armadilha

`page` do PyMuPDF é 0-indexado — a tela mostra `page + 1`. Se a sua tela e a resposta do
modelo discordarem da página, é quase certo que um dos dois esqueceu o `+ 1`.

## Gate — fechar a fase

Suba a interface e faça as três perguntas na tela, de olho no painel de fontes:

1. uma respondível → resposta + painel com documento, página, categoria e score
2. uma fora da base → recusa + painel dizendo que nada passou do limiar
3. uma de categoria nova (tarifa ou regimento) → citação apontando para o PDF certo

**Tire print das três.** Eles vão para o `app/README.md` e para o relatório de evolução —
é a evidência de "interface funcional com citação visível" que o avaliador procura, e
tirar agora custa 1 minuto contra reabrir tudo no dia 22.

```bat
python -m pytest tests -q
git add -A
git commit -m "Fase 3: interface Gradio com painel de fontes"
git push origin develop
```
