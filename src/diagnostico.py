"""
Diagnóstico do ambiente da Sprint 03.

    python -m src.diagnostico        (rodar da RAIZ do repositório)

Faz sete checagens e grava `docs/ambiente.md` com a tabela de versões. Esse
arquivo não é burocracia: o relatório de evolução precisa dizer em qual stack
os números foram medidos, e a rubrica pede os parâmetros de modelo documentados.
Gerar isso automaticamente evita a tabela desatualizada que todo grupo entrega.

A sétima checagem é a que ninguém lembra: se existe um SEGUNDO modelo
disponível. O bloco B (25 pts) exige comparar dois ou mais. Descobrir na véspera
que só há um modelo baixado é o tipo de problema que custa nota.
"""

import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

PACOTES = [
    "langchain", "langchain-core", "langchain-ollama",
    "langchain-classic", "langgraph", "pydantic", "tiktoken",
]

problemas: list[str] = []
avisos: list[str] = []
versoes: dict[str, str] = {}


def titulo(texto: str) -> None:
    print("\n" + "=" * 66)
    print(texto)
    print("=" * 66)


def ok(msg: str) -> None:
    print(f"  [ok ] {msg}")


def falha(msg: str) -> None:
    print(f"  [XX ] {msg}")
    problemas.append(msg)


def aviso(msg: str) -> None:
    print(f"  [ ! ] {msg}")
    avisos.append(msg)


# ---------------------------------------------------------------------------
titulo("1. PYTHON")
# ---------------------------------------------------------------------------
print(f"  {sys.version.split()[0]} em {platform.system()} {platform.release()}")
if sys.version_info < (3, 10):
    falha(f"Python {sys.version_info.major}.{sys.version_info.minor} é antigo demais para o LangChain 1.x")
else:
    ok("versão compatível")


# ---------------------------------------------------------------------------
titulo("2. PACOTES")
# ---------------------------------------------------------------------------
import importlib.metadata as meta  # noqa: E402

for pacote in PACOTES:
    try:
        v = meta.version(pacote)
        versoes[pacote] = v
        print(f"  [ok ] {pacote:<20} {v}")
    except meta.PackageNotFoundError:
        versoes[pacote] = "AUSENTE"
        falha(f"{pacote} não instalado")


# ---------------------------------------------------------------------------
titulo("3. VARIÁVEIS DE AMBIENTE")
# ---------------------------------------------------------------------------
host = (os.getenv("OLLAMA_HOST") or "").rstrip("/")
modelo = os.getenv("OLLAMA_MODEL") or ""
chave = (os.getenv("OLLAMA_API_KEY") or "").strip()
modelo_b = os.getenv("OLLAMA_MODEL_B") or ""

if not host:
    falha("OLLAMA_HOST ausente no .env")
else:
    ok(f"OLLAMA_HOST = {host}")

if not modelo:
    falha("OLLAMA_MODEL ausente no .env")
else:
    ok(f"OLLAMA_MODEL = {modelo}")

na_nuvem = "ollama.com" in host
if na_nuvem and not chave:
    falha("host aponta para a nuvem mas OLLAMA_API_KEY está vazia")
elif na_nuvem:
    # Nunca imprime a chave. Só confirma que existe e tem cara de chave.
    ok(f"OLLAMA_API_KEY presente ({len(chave)} caracteres)")
else:
    ok("modo local (sem chave necessária)")

if not modelo_b:
    aviso("OLLAMA_MODEL_B não definido - o bloco B da rubrica exige 2+ modelos")


# ---------------------------------------------------------------------------
titulo("4. CONEXÃO COM O OLLAMA")
# ---------------------------------------------------------------------------
disponiveis: list[str] = []

try:
    import httpx

    cabecalhos = {"Authorization": f"Bearer {chave}"} if chave else {}
    inicio = time.perf_counter()
    r = httpx.get(f"{host}/api/tags", headers=cabecalhos, timeout=15)
    latencia = (time.perf_counter() - inicio) * 1000
    r.raise_for_status()

    disponiveis = [m["name"] for m in r.json().get("models", [])]
    ok(f"servidor respondeu em {latencia:.0f} ms")
    print(f"       {len(disponiveis)} modelo(s): {', '.join(disponiveis[:6]) or '(nenhum)'}")

    # ATENÇÃO: /api/tags da ollama.com é PÚBLICO — responde 200 com ou sem
    # chave. Passar aqui não prova nada sobre a credencial. A validação de
    # verdade é um POST em /api/chat, abaixo. A versão anterior deste script
    # dava verde nesta seção e só descobria o 401 lá na seção 7.
    if na_nuvem:
        rc = httpx.post(
            f"{host}/api/chat",
            headers=cabecalhos,
            json={"model": modelo, "messages": [{"role": "user", "content": "ok"}],
                  "stream": False},
            timeout=60,
        )
        if rc.status_code == 401:
            falha("credencial recusada pela ollama.com (401) em /api/chat")
            print("       Rode: python -m src.teste_auth")
        elif rc.status_code == 404:
            falha(f"credencial ok, mas o modelo '{modelo}' não existe na nuvem (404)")
            print("       Rode: python -m src.teste_auth (seção 5 lista os válidos)")
        elif rc.status_code == 429:
            falha("credencial ok, mas a cota da conta estourou (429)")
        elif rc.status_code == 200:
            ok("credencial aceita em /api/chat")
        else:
            aviso(f"/api/chat devolveu {rc.status_code}")

except Exception as e:
    falha(f"não conectou em {host} ({type(e).__name__})")
    if na_nuvem:
        print("       Confira a chave em ollama.com/settings/keys")
    else:
        print("       O servidor local está rodando? Teste: ollama list")


# ---------------------------------------------------------------------------
titulo("5. MODELOS EXIGIDOS PELA RUBRICA")
# ---------------------------------------------------------------------------


def tem(nome: str) -> bool:
    """A nuvem às vezes omite a tag; compara pela base antes dos dois-pontos."""
    if not nome:
        return False
    base = nome.split(":")[0]
    return any(d == nome or d.split(":")[0] == base for d in disponiveis)


if disponiveis:
    if tem(modelo):
        ok(f"modelo principal disponível: {modelo}")
    else:
        falha(f"{modelo} não aparece na lista do servidor")

    if modelo_b and tem(modelo_b):
        ok(f"modelo de comparação disponível: {modelo_b}")
    elif modelo_b:
        aviso(f"{modelo_b} não encontrado - rode: ollama pull {modelo_b}")
else:
    aviso("sem lista de modelos - checagem pulada")


# ---------------------------------------------------------------------------
titulo("6. TIKTOKEN (medição de tokens do bloco B)")
# ---------------------------------------------------------------------------
try:
    import tiktoken

    codificador = tiktoken.get_encoding("cl100k_base")
    amostra = "Quanto tempo falta para minha recarga terminar?"
    n = len(codificador.encode(amostra))
    ok(f"encoding carregado - {n} tokens na frase de teste")
    print("       (cl100k_base é aproximação: o gpt-oss usa outro tokenizador,")
    print("        mas serve para comparar prompt v1 x v2 na MESMA régua)")
except Exception as e:
    falha(f"tiktoken falhou: {e} - precisa de internet no primeiro uso")


# ---------------------------------------------------------------------------
titulo("7. CHAIN LCEL DE PONTA A PONTA")
# ---------------------------------------------------------------------------
if problemas:
    aviso("pulando - resolva os itens acima primeiro")
else:
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        from src.chain.llm import get_llm

        chain = (
            ChatPromptTemplate.from_messages([
                ("system", "Responda em português, em uma única frase curta."),
                ("human", "{pergunta}"),
            ])
            | get_llm(perfil="classificador", num_predict=60)
            | StrOutputParser()
        )

        inicio = time.perf_counter()
        saida = chain.invoke({"pergunta": "O que significa kWh?"})
        segundos = time.perf_counter() - inicio

        ok(f"chain respondeu em {segundos:.2f}s")
        print(f"       > {saida.strip()[:160]}")

        if segundos > 20:
            aviso("latência alta - considere OLLAMA_THINK=none para o eval")

    except Exception as e:
        falha(f"chain falhou: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# RELATÓRIO
# ---------------------------------------------------------------------------
titulo("RESULTADO")

if problemas:
    print(f"  {len(problemas)} problema(s) bloqueante(s):")
    for p in problemas:
        print(f"    - {p}")
if avisos:
    print(f"  {len(avisos)} aviso(s):")
    for a in avisos:
        print(f"    - {a}")
if not problemas and not avisos:
    print("  Ambiente 100% pronto. Pode seguir para o passo 2.")
elif not problemas:
    print("  Ambiente funcional. Os avisos podem esperar.")

docs = RAIZ / "docs"
docs.mkdir(exist_ok=True)
destino = docs / "ambiente.md"

linhas = [
    "# Ambiente técnico — Sprint 03",
    "",
    f"Gerado automaticamente por `src/diagnostico.py` em "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M')}.",
    "",
    "## Plataforma",
    "",
    f"- Python {sys.version.split()[0]}",
    f"- {platform.system()} {platform.release()}",
    "",
    "## Versões fixadas",
    "",
    "| Pacote | Versão |",
    "|---|---|",
]
linhas += [f"| `{p}` | {v} |" for p, v in versoes.items()]
linhas += [
    "",
    "## Modelo",
    "",
    "| Item | Valor |",
    "|---|---|",
    f"| Host | `{host}` |",
    f"| Modo | {'Ollama Cloud' if na_nuvem else 'local'} |",
    f"| Modelo principal | `{modelo}` |",
    f"| Modelo de comparação | `{modelo_b or 'a definir'}` |",
    f"| Reasoning (`think`) | `{os.getenv('OLLAMA_THINK', 'low')}` |",
    "",
    "## Perfis de parâmetros",
    "",
    "Definidos em `src/chain/llm.py`. Cada perfil é uma decisão registrada.",
    "",
    "| Perfil | temperature | top_p | max_tokens | Uso |",
    "|---|---|---|---|---|",
    "| `classificador` | 0.0 | 1.0 | 160 | roteamento de intenção (reprodutível) |",
    "| `redator` | 0.2 | 0.9 | 400 | resposta ao usuário |",
    "| `estruturado` | 0.0 | 1.0 | 500 | saída Pydantic (JSON válido de primeira) |",
    "",
]

destino.write_text("\n".join(linhas), encoding="utf-8")
print(f"\n  Tabela de versões gravada em: {destino.relative_to(RAIZ)}")
print("=" * 66)

raise SystemExit(1 if problemas else 0)