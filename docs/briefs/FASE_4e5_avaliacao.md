# Fases 4 e 5 — Avaliação · 18 a 21/10

> Cole este arquivo inteiro como primeira mensagem numa sessão de Claude Code aberta na
> raiz do repositório. O `CLAUDE.md` já carrega sozinho.
>
> Duas fases, um brief, porque são o mesmo código rodado duas vezes.
> **Fase 4 (18–19/10):** RAGAS no ar, iteração 1 medida, resultado analisado.
> **Fase 5 (20–21/10):** prompt v2 + chunking ajustado, iteração 2, ganho demonstrado.

## Objetivo

Bloco C inteiro (25 pts) e metade do D (10 pts): RAGAS medindo o pipeline, duas iterações
com ganho e o relatório de modelos e parâmetros.

**Este é o caminho crítico e não é comprimível.** O ganho da segunda iteração só existe
depois da primeira, e o bloco D inteiro depende disso. Se a Fase 1 ou a 3 atrasarem, elas
cedem dias para cá — nunca o contrário. Se a Fase 4 não começar até **19/10**, pare tudo,
corte escopo pela lista do roadmap e rode o eval.

## Decisão a tomar até 16/10

**RAGAS ou rubrica manual.** O §4 aceita as duas, sem penalidade, desde que a manual seja
documentada e aplicada no mesmo eval set. Tente o RAGAS primeiro — `ragas==0.4.3` e
`datasets==5.0.1` já estão fixados e o import foi validado. Se quebrar, caia no fallback
sem drama, mas **decida cedo**, não na véspera.

## Entregável 1 — `evals/ragas_eval.py`

Configuração do RAGAS com Ollama (a oficial usa OpenAI por padrão, que é paga):

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from datasets import Dataset

ragas_llm = LangchainLLMWrapper(get_llm(temperature=0))
ragas_embs = LangchainEmbeddingsWrapper(OllamaEmbeddings(model="nomic-embed-text"))
faithfulness.llm = ragas_llm
answer_relevancy.llm = ragas_llm
answer_relevancy.embeddings = ragas_embs

dados = {
    "question": PERGUNTAS,
    "answer":   [chain_rag.invoke(q) for q in PERGUNTAS],
    "contexts": [[d.page_content for d in retriever.invoke(q)] for q in PERGUNTAS],
}
res = evaluate(Dataset.from_dict(dados), metrics=[faithfulness, answer_relevancy])
```

As perguntas vêm de `evals/eval_set_rag.json`, que o Kayo monta na F3. **Não invente eval
set próprio** — a comparação entre iterações exige o mesmo conjunto nas duas pontas.

Grave cada execução em `evals/resultados/ragas_<iteracao>_<carimbo>.json`, com os
parâmetros junto do score: `chunk_size`, `chunk_overlap`, `k`, `temperature`, `top_p`,
`max_tokens`, `seed`, modelo, versão do prompt. Sem isso o número não é reproduzível e
não serve para o relatório.

## Entregável 2 — fallback manual (escreva mesmo que o RAGAS funcione)

`evals/juiz_rag.py`, com LLM-as-judge e rubrica 0–1. O padrão da Aula 07:

```
<tarefa>Avalie se a RESPOSTA está fundamentada no CONTEXTO.</tarefa>
<contexto>{contexto}</contexto>
<resposta>{resposta}</resposta>
Responda APENAS com um número de 0 a 1:
- 1.0: toda a resposta está no contexto
- 0.5: resposta parcialmente no contexto
- 0.0: resposta inventa informações não presentes no contexto
```

Faça o mesmo para `answer_relevancy` (a resposta aborda o que foi perguntado?).
`float(resultado.strip())` dentro de `try/except ValueError`, devolvendo `-1.0` como
sentinela de score inválido — o modelo às vezes devolve texto junto.

Registre os critérios da rubrica em `evals/rubrica_manual.md` e **justifique a
equivalência** com as métricas do RAGAS. O §4 pede isso explicitamente.

Custo baixo e seguro: se o RAGAS quebrar na véspera, você já tem o número.

## Entregável 3 — as duas iterações

| | Iteração 1 | Iteração 2 |
|---|---|---|
| Chunking | `chunk_size=800`, `overlap=100` (baseline da Aula 06) | o melhor entre 512 e 1024, `overlap = size // 8` |
| Prompt RAG | `v1` | `v2`, corrigindo o que a iteração 1 mostrou |
| k | 3 | 3 ou 5, conforme a medição |

Rode a iteração 1, **leia os scores antes de mexer em qualquer coisa**, e deixe o
diagnóstico guiar a iteração 2:

- `faithfulness` baixo → o modelo inventa. Reforce o grounding no prompt, confirme
  `temperature=0`, verifique se os chunks certos estão vindo.
- `answer_relevancy` baixo → responde, mas não à pergunta. Problema de retriever: suba
  `k`, ajuste `chunk_size`.

Compare também **chunk_size 256 / 512 / 1024** no mesmo corpus, como a demo da Aula 07.
Esse quadro é insumo direto do relatório e mostra método.

## Entregável 4 — `docs/relatorio_modelos.md`

Exigido nominalmente pelo §6. Compare **2+ modelos** (`gpt-oss:120b` e `gemma4:31b` já
estão na linha de base) documentando, para cada um: `temperature`, `k` (top-k do
retriever), `top_p`, `max_tokens`, mais latência e tokens por turno.

`src/chain/llm.py` já documenta os perfis de parâmetro e `src/chain/multi_provider.py` já
monta a matriz modelo × prompt em `RunnableParallel`. **Reaproveite os dois** — e
re-execute o multi-provider com os prompts RAG, o que fecha o bônus de +1 ponto quase de
graça.

Resgate o arquivo antigo para referência de formato:
`git show sprint3-final:docs/relatorio_modelos.md`

## Entregável 5 — `prompts/versoes_rag.md`

Tabela de versões do prompt RAG: versão, arquivo, tokens, o que mudou, por quê, **ganho
medido**. A coluna de ganho fica em branco até o eval rodar — é a regra do grupo, e está
certa.

Use `prompts/versoes.md` como modelo (recupere com
`git show sprint3-final:prompts/versoes.md`). Ele tem um acerto que vale repetir: uma
coluna de controle isolando o efeito do framework do efeito do prompt.

## Critérios de aceite

- [ ] `python -m evals.ragas_eval --iteracao 1` roda e grava JSON com scores e parâmetros
- [ ] Iteração 2 roda no **mesmo** eval set e mostra ganho
- [ ] Ganho explicado por uma hipótese, não só reportado
- [ ] Pelo menos 1 pergunta com score baixo analisada: quais chunks vieram, por que falhou, o que fazer
- [ ] `docs/relatorio_modelos.md` com 2+ modelos e os 4 parâmetros do §6
- [ ] `prompts/versoes_rag.md` com ganho medido preenchido
- [ ] Fallback manual escrito e documentado, usado ou não
- [ ] Entrada no `docs/CHANGELOG_SPRINT4.md` com a saída dos comandos colada

## Armadilhas registradas

- **Não suba versão de pacote.** `ragas 0.4.3` quebra no import com
  `langchain-community 0.4.2`. O pin é `0.4.1`, e isso já custou um dia ao grupo.
- `evals/baseline_sprint3/` é a coluna "antes" do relatório, congelada e medida com modelo
  real. Não toque.
- O prompt `v2` da Sprint 3 **nunca foi medido com modelo real** — a execução de 20/09
  rodou contra o servidor falso de testes. Se citar esse número em qualquer lugar, cite
  como não medido.
- Rode a iteração 1 cedo. As duas iterações dependem do Ollama Cloud, e uma queda na
  véspera custa o bloco D inteiro. `local:qwen3:8b` é o plano B, já previsto no `.env.example`.

## Gate da Fase 4 (19/10) — não avance sem

- [ ] Existe `evals/resultados/ragas_1_<carimbo>.json` com faithfulness, answer_relevancy
      **e todos os parâmetros** (`chunk_size`, `chunk_overlap`, `k`, `temperature`,
      `top_p`, `max_tokens`, `seed`, modelo, versão do prompt)
- [ ] Você sabe dizer, em uma frase, **o que o número diz que está errado**

Essa segunda linha é o gate de verdade. Um score sem diagnóstico não gera iteração 2 —
gera um chute. Use a tabela de interpretação da Aula 07: faithfulness baixo aponta para
grounding ou retriever; answer_relevancy baixo aponta para `k` ou `chunk_size`.

## Gate da Fase 5 (21/10) — não avance sem

- [ ] Iteração 2 rodada no **mesmo** eval set, com `prompt_rag` v2 e/ou chunking ajustado
- [ ] **Ganho medido**, com a hipótese que o explica escrita junto
- [ ] 1 pergunta de score baixo analisada: quais chunks vieram e por que falhou
- [ ] `prompts/versoes_rag.md` com a coluna de ganho preenchida
- [ ] `docs/relatorio_modelos.md` com 2+ modelos e os 4 parâmetros do §6

Se a iteração 2 **piorar** o score, não esconda. Registre, explique a hipótese e rode uma
terceira com o ajuste contrário. Um relatório que mostra uma tentativa fracassada e a
correção vale mais, no bloco D, do que um número bonito sem história.

```bat
git add -A
git commit -m "Fases 4 e 5: RAGAS nas duas iteracoes com ganho medido"
git push origin develop
```

Cole as duas saídas no changelog, lado a lado. Elas são a tabela antes/depois da Fase 6
quase pronta.
