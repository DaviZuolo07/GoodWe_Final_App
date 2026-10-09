# Passo 0 — arrancar a Sprint 04

Faça na ordem. São ~20 minutos. Até o passo 4 estar feito, ninguém do grupo consegue
clonar o estado certo do projeto.

Tudo abaixo foi testado numa cópia do seu repositório: zero conflitos, árvore final de
54 arquivos idêntica ao `develop`.

---

## 0.1 — Trocar a chave do Ollama (2 min, faça primeiro)

A `OLLAMA_API_KEY` do `.env` saiu da máquina dentro de um zip. Nunca foi commitada — o
histórico está limpo e a penalidade do §10 não se aplica — mas a chave vazou e é a segunda
vez que isso acontece.

1. Abra <https://ollama.com/settings/keys>
2. Revogue a chave atual e gere outra
3. Guarde a nova; ela entra no `.env` no passo 0.5

**Não pule e não deixe para depois.** O resto do passo 0 depende de uma chave válida.

---

## 0.2 — Rede de segurança

```bat
cd C:\Users\labsfiap\Downloads\GoodWe_Final_App

xcopy /E /I /H /Y . ..\GoodWe_BACKUP_09102026

git fetch origin --prune --tags
git status
```

O `git fetch` é obrigatório: seu `origin/main` local está desatualizado. Alguém mergeou a
PR #1 e apagou as três `feature/*` no GitHub depois que o zip foi feito.

Se o `git status` mostrar algo em **Changes to be committed** ou **Changes not staged**,
pare e resolva antes de seguir. Na última verificação não havia nada.

---

## 0.3 — Subir a tag para o GitHub

```bat
git push origin sprint3-final
git ls-remote --tags origin
```

A segunda linha **tem** que imprimir `refs/tags/sprint3-final`.

Hoje essa tag existe num disco só — o seu. Ela é a única cópia das Sprints 1–3, e o passo
seguinte apaga 62 arquivos. Não avance sem ver a tag no remoto.

---

## 0.4 — Limpar, mergear, publicar

```bat
REM 1. ver o que seria apagado, sem apagar
git clean -nd

REM 2. apagar (NUNCA use -x: ele levaria o .env e a venv junto)
git clean -fd

REM 3. atualizar a main e mergear
git switch main
git merge --ff-only origin/main
git merge develop

REM 4. conferir ANTES de empurrar — tem que dar 54
git ls-files | find /c /v ""

REM 5. publicar e realinhar
git push origin main
git switch develop
git merge --ff-only main
git push origin develop

REM 6. podar as branches mortas (só locais; o GitHub já não as tem)
git branch -d feature/ai-davi feature/backend-crepe feature/frontend-gus

REM 7. conferir o resultado
git branch -a
git log --oneline --graph --decorate --all -8
```

O esperado no final: só `main` e `develop`, locais e remotas, no mesmo commit de merge.
Nenhuma `feature/*`.

O realinhamento do item 5 não é opcional — é ele que faz o próximo release
`develop` → `main` voltar a ser fast-forward.

---

## 0.5 — Reconstruir o `.env`

O `.env` atual está fora de sincronia: tem `MODELO_JUIZ` (variável morta, o juiz foi
apagado na F0), tem `OLLAMA_MODEL_B` e `OLLAMA_THINK` duplicados, e **falta**
`PROMPT_VERSAO`, `MEMORIA_MAX_TOKENS` e `EXTRACAO_FORMATO`.

```bat
copy .env .env.backup-local
copy .env.example .env
```

Agora abra o `.env` e cole a chave **nova** do passo 0.1. Depois acrescente as duas linhas
que a Sprint 04 vai precisar:

```
EMBEDDING_MODEL=nomic-embed-text
CHROMA_DIR=chroma_db
```

Confirme que continua ignorado:

```bat
git check-ignore -v .env
```

Tem que imprimir `.gitignore:22:.env`. Se não imprimir nada, **pare** — o `.env` não está
protegido.

---

## 0.6 — A pergunta que decide o desenho da F2

```bat
python -m src.teste_auth
```

Procure **`nomic-embed-text`** na lista de modelos da conta.

- **Aparece** → siga o plano como está.
- **Não aparece** → avise o grupo hoje. O §3 item 1 pede esse modelo pelo nome; sem ele a
  F2 muda de desenho e é melhor saber agora do que na segunda.

Aproveite e confirme o ambiente:

```bat
python --version
python -m pytest tests -q
python -m evals.guardrails_eval
```

Esperado: **111 testes passando** e **39/39 ataques bloqueados, 0 falso positivo**.

Atenção ao Python: a `venv` da máquina é 3.14 e os pins foram testados em 3.13. Se a
instalação reclamar, recrie a venv em 3.13 — principalmente na máquina de quem for rodar
o eval.

---

## 0.7 — Instalar o kit e commitar

Copie para a raiz do repositório:

- `CLAUDE.md`
- `ROADMAP_SOLO.md`
- `docs/briefs/FASE_1_pipeline_rag.md`
- `docs/briefs/FASE_2_base_conhecimento.md`
- `docs/briefs/FASE_3_interface.md`
- `docs/briefs/FASE_4e5_avaliacao.md`
- `docs/briefs/FASE_6_relatorios.md`
- `PASSO_0.md` (este arquivo)

```bat
git add CLAUDE.md ROADMAP_SOLO.md PASSO_0.md docs/briefs
git commit -m "Contrato de trabalho, roadmap e briefs das fases da Sprint 04"
git push origin develop
```

---

## 0.8 — Cada integrante, na própria máquina (1 min)

O §10 exige "commits regulares **de cada integrante**". Hoje os 11 commits são todos seus.
Isso não se conserta na véspera.

```bat
git config --global user.name "Nome Sobrenome"
git config --global user.email "email-do-github@exemplo.com"
```

Confira depois de alguns dias:

```bat
git shortlog -sn
```

Se continuar com um nome só, o grupo está quebrando uma condição de entrega.

---

## Decisões que ainda precisam do grupo

- [ ] Confirmar a divisão de frentes (ou redistribuir)
- [ ] **Até 16/10**: RAGAS ou rubrica manual
- [ ] Estratégia de chunking: tamanho e overlap, **com justificativa** (o §4 cobra a
      estratégia documentada)
- [ ] Quem adapta `prompts/versoes.md` para o prompt RAG
      (`git show sprint3-final:prompts/versoes.md`)

---

## Depois do passo 0

Abra **`ROADMAP_SOLO.md`**. Ele tem o cronograma dia a dia, os gates de cada fase e a
ordem de corte de escopo.

Em resumo: **uma sessão de Claude Code por fase**, na raiz do repositório, com o brief da
fase colado como primeira mensagem. O `CLAUDE.md` carrega sozinho e já leva contrato,
stack e invariantes. Não emende duas fases na mesma sessão — o changelog é o handoff.

A próxima coisa a fazer é a **Fase 1 (pipeline RAG)**, contra os 3 PDFs que já estão
indexados. Ela não espera a base expandida.
