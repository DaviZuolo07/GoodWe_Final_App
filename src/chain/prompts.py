"""
Carregador de prompts versionados (prompts/system_prompt_vN.md).

Cada arquivo tem um cabeçalho mínimo:

    ---
    versao: v2
    data: 2026-09-15
    humano: <pergunta_usuario>\n{pergunta}\n</pergunta_usuario>
    ---
    (corpo = template do system prompt)

O prompt deixa de ser uma string no meio do código e vira artefato versionado:
trocar de versão é um argumento (`versao="v1"`), e o eval mede cada versão com
o mesmo runner. É isso que alimenta a tabela de versões do §6.
"""

from __future__ import annotations

import functools
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.chain import tokens

RAIZ = Path(__file__).resolve().parents[2]
PASTA_PROMPTS = RAIZ / "prompts"
VERSAO_PADRAO = os.getenv("PROMPT_VERSAO", "v2")

# Canário: string aleatória por processo, embutida no system prompt. Se ela
# aparecer numa resposta, houve vazamento do prompt — o guardrail de saída
# troca a resposta por uma recusa. Técnica de "canary token" para detecção de
# prompt leaking (OWASP Top 10 for LLM Applications 2025, LLM07).
CANARIO = os.getenv("PROMPT_CANARIO") or f"CANARIO-{secrets.token_hex(4).upper()}"


@dataclass(frozen=True)
class PromptVersionado:
    versao: str
    data: str
    sistema: str
    humano: str
    caminho: Path

    @property
    def variaveis(self) -> set[str]:
        return set(re.findall(r"\{(\w+)\}", self.sistema + self.humano))

    def usa(self, variavel: str) -> bool:
        return variavel in self.variaveis


def versoes_disponiveis() -> list[str]:
    achados = sorted(PASTA_PROMPTS.glob("system_prompt_v*.md"),
                     key=lambda p: int(re.search(r"v(\d+)", p.stem).group(1)))
    return [re.search(r"(v\d+)", p.stem).group(1) for p in achados]


@functools.lru_cache(maxsize=16)
def carregar(versao: str = VERSAO_PADRAO) -> PromptVersionado:
    caminho = PASTA_PROMPTS / f"system_prompt_{versao}.md"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não existe. Versões: {versoes_disponiveis()}")

    texto = caminho.read_text(encoding="utf-8").replace("\r\n", "\n")
    cab = re.match(r"^---\n(.*?)\n---\n", texto, flags=re.S)
    if not cab:
        raise ValueError(f"{caminho.name}: cabeçalho --- ausente")

    meta = {}
    for linha in cab.group(1).splitlines():
        chave, _, valor = linha.partition(":")
        meta[chave.strip()] = valor.strip()

    return PromptVersionado(
        versao=meta.get("versao", versao),
        data=meta.get("data", ""),
        sistema=texto[cab.end():].strip(),
        humano=meta.get("humano", "{pergunta}").replace("\\n", "\n"),
        caminho=caminho,
    )


@functools.lru_cache(maxsize=1)
def base_produtos() -> dict:
    return json.loads((PASTA_PROMPTS / "base_produtos.json").read_text(encoding="utf-8"))


def base_produtos_texto() -> str:
    base = base_produtos()
    linhas = []
    for p in base["produtos"]:
        linhas.append(
            f"- {p['modelo']}: {p['tipo']}, {str(p['potencia_maxima_kw']).replace('.', ',')} kW, "
            f"conector {p['conector']}, {p['tensao_v']} V, {p['corrente_maxima_a']} A, "
            f"{p['fases']}, {p['unidades_no_condominio']} unidade(s) no condomínio"
        )
    tarifa = str(base["tarifa_condominio_brl_kwh"]).replace(".", ",")
    linhas.append(f"- Tarifa de recarga do condomínio: R$ {tarifa} por kWh")
    return "\n".join(linhas)


def modelos_na_base() -> set[str]:
    return {p["modelo"].lower() for p in base_produtos()["produtos"]}


def montar_template(versao: str = VERSAO_PADRAO) -> ChatPromptTemplate:
    """
    system (versionado) + histórico (memória) + humano (com delimitadores).

    O MessagesPlaceholder("historico") é onde o RunnableWithMessageHistory
    injeta a janela da ConversationTokenBufferMemory.
    """
    pv = carregar(versao)
    template = ChatPromptTemplate.from_messages([
        ("system", pv.sistema),
        MessagesPlaceholder("historico", optional=True),
        ("human", pv.humano),
    ])
    fixos = {}
    if pv.usa("base_produtos"):
        fixos["base_produtos"] = base_produtos_texto()
    if pv.usa("canario"):
        fixos["canario"] = CANARIO
    return template.partial(**fixos) if fixos else template


def tokens_do_sistema(versao: str) -> int:
    """Tokens do system prompt renderizado com os blocos dinâmicos vazios."""
    pv = carregar(versao)
    vazio = {v: "" for v in pv.variaveis}
    vazio.update({"base_produtos": base_produtos_texto(), "canario": CANARIO})
    return tokens.contar(pv.sistema.format(**vazio))


def tokens_legado() -> int:
    """
    Tokens do contexto fixo que o legado (Sprint 2) envia em TODA chamada:
    system_prompt.txt + GOODWE_CONTEXT + few_shots.txt, como mensagens system
    separadas (ver ai/agents/chargeops_agent.py). Leitura apenas — o legado
    não é alterado.
    """
    import ast

    pasta = RAIZ / "ai"
    sistema = (pasta / "prompts" / "system_prompt.txt").read_text(encoding="utf-8")
    few = (pasta / "prompts" / "few_shots.txt").read_text(encoding="utf-8")
    fonte = (pasta / "context" / "goodwe_context.py").read_text(encoding="utf-8")
    contexto = ""
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Assign) and getattr(no.targets[0], "id", "") == "GOODWE_CONTEXT":
            contexto = ast.literal_eval(no.value)
    return tokens.contar_mensagens([
        {"content": sistema}, {"content": contexto}, {"content": few},
    ])
