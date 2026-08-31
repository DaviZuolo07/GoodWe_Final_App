"""
Isolador de falha de autenticação do Ollama Cloud.

    python -m src.teste_auth        (rodar da RAIZ do repositório)

Existe porque o diagnóstico anterior deu um falso verde. Ele testava a conexão
com `GET /api/tags` — e esse endpoint da ollama.com é PÚBLICO: responde 200 com
ou sem chave. A primeira chamada que realmente exigia credencial era a chain, e
por isso o 401 só apareceu no fim.

Este script faz o oposto: testa cada camada isoladamente, na ordem, e para na
primeira que quebrar. Em vez de "falhou", ele diz QUAL das quatro coisas falhou:
a chave, o endpoint, o cliente do Ollama, ou a integração do LangChain.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

HOST = (os.getenv("OLLAMA_HOST") or "https://ollama.com").strip().rstrip("/")
MODELO = (os.getenv("OLLAMA_MODEL") or "gpt-oss:120b").strip()
BRUTA = os.getenv("OLLAMA_API_KEY") or ""
CHAVE = BRUTA.strip().strip('"').strip("'")

MENSAGEM = [{"role": "user", "content": "Responda apenas: ok"}]


def secao(n: int, titulo: str) -> None:
    print(f"\n{'=' * 66}\n{n}. {titulo}\n{'=' * 66}")


def parar(diagnostico: str, acao: str) -> None:
    print(f"\n{'!' * 66}")
    print(f"CAUSA PROVÁVEL: {diagnostico}")
    print(f"O QUE FAZER:    {acao}")
    print("!" * 66)
    sys.exit(1)


# ---------------------------------------------------------------------------
secao(0, "FORMATO DA CHAVE (sem imprimir a chave)")
# ---------------------------------------------------------------------------
if not BRUTA:
    parar("OLLAMA_API_KEY não existe no .env",
          "Crie a chave em https://ollama.com/settings/keys e cole no .env")

print(f"  comprimento bruto ....... {len(BRUTA)}")
print(f"  comprimento limpo ....... {len(CHAVE)}")
print(f"  começa com .............. {CHAVE[:4]}…")
print(f"  termina com ............. …{CHAVE[-4:]}")

sujeira = []
if BRUTA != BRUTA.strip():
    sujeira.append("espaço ou quebra de linha nas pontas")
if BRUTA.strip() != CHAVE:
    sujeira.append("aspas em volta do valor")
if "\n" in BRUTA or "\r" in BRUTA:
    sujeira.append("quebra de linha NO MEIO da chave (colagem partida)")
if " " in CHAVE:
    sujeira.append("espaço no meio da chave")
if "cole_a_chave" in CHAVE or "sua_chave" in CHAVE:
    parar("o .env ainda tem o texto de exemplo, não a chave real",
          "Substitua o valor de OLLAMA_API_KEY pela chave de verdade")

if sujeira:
    print("  [ ! ] sujeira detectada: " + "; ".join(sujeira))
    print("        (o código já limpa, mas vale corrigir o .env)")
else:
    print("  [ok ] chave limpa")

print(f"\n  host .................... {HOST}")
print(f"  modelo .................. {MODELO}")

if MODELO.endswith("-cloud") and "ollama.com" in HOST:
    print("  [ ! ] o sufixo '-cloud' é para o Ollama LOCAL puxando da nuvem.")
    print("        Falando direto com ollama.com, o nome é sem sufixo.")


# ---------------------------------------------------------------------------
secao(1, "GET /api/tags SEM chave  (deve dar 200 — endpoint público)")
# ---------------------------------------------------------------------------
try:
    r = httpx.get(f"{HOST}/api/tags", timeout=20)
    print(f"  status {r.status_code}")
    if r.status_code == 200:
        modelos = [m.get("name") for m in r.json().get("models", [])]
        print(f"  {len(modelos)} modelo(s) no catálogo público")
        print("  [ok ] confirmado: /api/tags NÃO valida credencial.")
        print("        Era esse o falso verde do diagnóstico anterior.")
except Exception as e:
    print(f"  [XX ] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
secao(2, "POST /api/chat SEM chave  (deve dar 401 — aqui a auth importa)")
# ---------------------------------------------------------------------------
try:
    r = httpx.post(f"{HOST}/api/chat",
                   json={"model": MODELO, "messages": MENSAGEM, "stream": False},
                   timeout=30)
    print(f"  status {r.status_code}")
    if r.status_code == 401:
        print("  [ok ] confirmado: /api/chat exige credencial")
    elif r.status_code == 200:
        print("  [ ! ] respondeu sem chave — host não é a nuvem oficial?")
except Exception as e:
    print(f"  [XX ] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
secao(3, "POST /api/chat COM chave  (o teste de verdade)")
# ---------------------------------------------------------------------------
try:
    r = httpx.post(
        f"{HOST}/api/chat",
        headers={"Authorization": f"Bearer {CHAVE}"},
        json={"model": MODELO, "messages": MENSAGEM, "stream": False},
        timeout=60,
    )
    print(f"  status {r.status_code}")

    if r.status_code == 401:
        print(f"  corpo: {r.text[:300]}")
        parar(
            "a chave foi enviada corretamente e a ollama.com recusou.\n"
            "                O problema é a CREDENCIAL, não o código.",
            "Em https://ollama.com/settings/keys: apague a chave antiga, gere\n"
            "                uma nova e cole inteira. Confirme também que a conta\n"
            "                está logada (ollama signin) e tem acesso à nuvem.",
        )

    if r.status_code == 404:
        print(f"  corpo: {r.text[:300]}")
        parar(f"a chave é válida mas o modelo '{MODELO}' não foi encontrado",
              "Rode a seção 5 abaixo e escolha um nome da lista real")

    if r.status_code == 429:
        parar("chave válida, mas a cota da conta estourou",
              "Veja https://ollama.com/pricing ou espere a janela resetar")

    r.raise_for_status()
    conteudo = (r.json().get("message") or {}).get("content", "")
    print(f"  [ok ] resposta: {conteudo.strip()[:120]}")

except SystemExit:
    raise
except Exception as e:
    parar(f"{type(e).__name__}: {e}", "Falha de rede, proxy ou firewall")


# ---------------------------------------------------------------------------
secao(4, "MESMA CHAMADA VIA ChatOllama  (integração LangChain)")
# ---------------------------------------------------------------------------
try:
    from src.chain.llm import get_llm

    modelo = get_llm(perfil="classificador", num_predict=30)
    cliente_http = modelo._client._client
    tem_header = "authorization" in cliente_http.headers
    print(f"  header Authorization chegou no httpx: {tem_header}")

    if not tem_header:
        parar("o ChatOllama foi construído sem o header de autenticação",
              "Confirme que OLLAMA_HOST contém 'ollama.com' no .env")

    resposta = modelo.invoke("Responda apenas: ok")
    print(f"  [ok ] {str(resposta.content).strip()[:120]}")
    print("\n  Se a seção 3 passou e esta falhou, o problema é a integração.")
    print("  Se as duas passaram, o ambiente está pronto.")

except SystemExit:
    raise
except Exception as e:
    print(f"  [XX ] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
secao(5, "MODELOS QUE A SUA CHAVE ENXERGA")
# ---------------------------------------------------------------------------
# O catálogo da nuvem muda: modelos são aposentados e substituídos. Em vez de
# chutar nomes, perguntamos ao servidor. Esta lista é a fonte de verdade para
# escolher o segundo modelo do relatório (bloco B da rubrica).
try:
    r = httpx.get(f"{HOST}/api/tags",
                  headers={"Authorization": f"Bearer {CHAVE}"}, timeout=20)
    r.raise_for_status()
    nomes = sorted(m.get("name", "") for m in r.json().get("models", []))
    print(f"  {len(nomes)} modelo(s):\n")
    for n in nomes:
        marca = "  <- principal" if n == MODELO else ""
        print(f"    {n}{marca}")

    destino = RAIZ / "docs" / "modelos_disponiveis.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(nomes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Lista salva em docs/modelos_disponiveis.json")
except Exception as e:
    print(f"  [XX ] {type(e).__name__}: {e}")

print("\n" + "=" * 66)
