"""
Builder da chain LCEL — o núcleo conversacional refatorado.

    prompt | llm | parser

É o item 1 do escopo e o bloco A da rubrica (40 pts, o maior peso). A chain
existe aqui de forma isolada e testável de propósito: quando o LangGraph entrar
como camada extra, os nós vão CHAMAR esta chain, não substituí-la. Se o grafo
engolisse a chain, a rubrica perderia justamente o que quer ver.

    from src.chain.builder import ChargeOpsChain
    chat = ChargeOpsChain()
    print(chat.responder("Quanto tempo leva para carregar?", persona="morador"))

POR QUE O PROMPT VEM DE ARQUIVO
-------------------------------
`prompts/system_prompt_vN.md` é carregado em runtime, não embutido no código.
Isso é o que torna a tabela de versões do §6 possível: trocar de versão é mudar
um argumento, e o eval mede as duas com tudo o mais idêntico. Prompt hardcoded
não é versionável — é só uma string que alguém editou.
"""

import os
import re
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.chain.execucao import _ACEITA_RACIOCINIO, _registrar
from src.chain.llm import get_llm, nome_do_modelo

RAIZ = Path(__file__).resolve().parent.parent.parent
PASTA_PROMPTS = RAIZ / "prompts"

VERSAO_PADRAO = "v1"

# Front matter YAML-ish entre --- no topo do .md: metadado para humanos.
# É removido antes de enviar ao modelo — senão a justificativa da versão
# entraria no prompt e ainda seria contada como token.
_FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


def carregar_prompt(versao: str = VERSAO_PADRAO) -> str:
    """Texto do system prompt, sem o front matter."""
    if os.getenv("PROMPT_DEV") == "1":
        return _ler(versao)          # sem cache: editar o .md reflete na hora
    return _ler_cache(versao)


def _ler(versao: str) -> str:
    caminho = PASTA_PROMPTS / f"system_prompt_{versao}.md"
    if not caminho.exists():
        disponiveis = sorted(p.name for p in PASTA_PROMPTS.glob("system_prompt_*.md"))
        raise FileNotFoundError(
            f"{caminho} não existe. Versões disponíveis: {disponiveis or 'nenhuma'}"
        )
    return _FRONT_MATTER.sub("", caminho.read_text(encoding="utf-8")).strip()


@lru_cache(maxsize=8)
def _ler_cache(versao: str) -> str:
    return _ler(versao)


def contar_tokens(texto: str) -> int:
    """Medição para a tabela de versões (aproximada, mas a MESMA régua sempre)."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(texto or ""))
    except Exception:
        return len((texto or "").split())


def montar_contexto(persona: str = "morador", perfil: dict | None = None) -> str:
    """
    Bloco de contexto do usuário.

    Em v1 é texto simples com rótulos. A v2 vai reescrever isto com XML tagging
    (Aula 04) — e a diferença de tokens entre as duas formas é justamente o
    ganho que a tabela de versões precisa mostrar.
    """
    linhas = [f"Persona do usuário: {persona}"]
    rotulos = {
        "name": "Nome", "car_model": "Veículo", "battery_kwh": "Bateria (kWh)",
        "charger_kw": "Potência do carregador (kW)", "block": "Bloco",
        "apartment": "Apartamento",
    }
    for chave, valor in (perfil or {}).items():
        if chave == "persona" or valor in (None, ""):
            continue
        linhas.append(f"{rotulos.get(chave, chave)}: {valor}")

    if len(linhas) == 1:
        linhas.append("(sem dados de perfil cadastrados)")
    return "\n".join(linhas)


def construir_prompt(versao: str = VERSAO_PADRAO) -> ChatPromptTemplate:
    """
    O template de mensagens.

    O system prompt entra como SystemMessage pronta, não como template: o .md
    pode conter chaves { } e o ChatPromptTemplate as leria como variável,
    quebrando por um caractere de texto. Só o que é dinâmico é template.

    `historico` é opcional e já está posicionado. É o encaixe da memória do
    passo 5 — quando o RunnableWithMessageHistory entrar, a chain não muda.
    """
    return ChatPromptTemplate.from_messages([
        SystemMessage(content=carregar_prompt(versao)),
        ("system", "Dados do usuário atual:\n{contexto}"),
        MessagesPlaceholder("historico", optional=True),
        ("human", "{pergunta}"),
    ])


def construir_chain(
    versao: str = VERSAO_PADRAO,
    perfil_llm: str = "redator",
    papel: str = "principal",
    model: str | None = None,
    reasoning=None,
    **kwargs,
):
    """A chain LCEL: prompt | llm | parser."""
    return (
        construir_prompt(versao)
        | get_llm(perfil=perfil_llm, papel=papel, model=model,
                  reasoning=reasoning, seed=42, **kwargs)
        | StrOutputParser()
    )


class ChargeOpsChain:
    """
    Embrulho fino sobre a chain, com uma responsabilidade extra: sobreviver a
    modelos que não aceitam o parâmetro de raciocínio.

    O `gemma4:31b` devolveu string vazia em 23 de 23 casos por causa do `think`,
    e o `gpt-oss:20b` fez o mesmo como juiz. Como o bloco B exige comparar 2+
    modelos, a chain precisa funcionar em famílias diferentes — senão a
    comparação morre antes de começar. A decisão é memorizada por modelo, então
    o custo é uma chamada extra por modelo, uma vez na sessão.
    """

    def __init__(self, versao: str = VERSAO_PADRAO, model: str | None = None,
                 papel: str = "principal", perfil_llm: str = "redator",
                 guardrails: bool = False, **kwargs):
        self.versao = versao
        self.guardrails = guardrails
        self.ultimo_bloqueio: dict = {}
        self.modelo = model or nome_do_modelo(papel)
        self.perfil_llm = perfil_llm
        self._kwargs = kwargs
        self._chains: dict = {}

    def _chain(self, com_raciocinio: bool):
        if com_raciocinio not in self._chains:
            self._chains[com_raciocinio] = construir_chain(
                versao=self.versao, perfil_llm=self.perfil_llm,
                model=self.modelo,
                reasoning=None if com_raciocinio else False,
                **self._kwargs,
            )
        return self._chains[com_raciocinio]

    def prompt_renderizado(self, pergunta: str, persona="morador", perfil=None) -> str:
        msgs = construir_prompt(self.versao).format_messages(
            contexto=montar_contexto(persona, perfil), pergunta=pergunta
        )
        return "\n".join(str(m.content) for m in msgs)

    def responder(self, pergunta: str, persona="morador", perfil=None,
                  historico=None) -> str:
        self.ultimo_bloqueio = {}

        # PRÉ-CHECK determinístico. Quando bloqueia, o modelo não é chamado:
        # nenhuma latência, nenhum token, nenhuma chance de ser convencido.
        if self.guardrails:
            from src.guardrails import avaliar_entrada
            liberado, recusa, diagnostico = avaliar_entrada(pergunta)
            if not liberado:
                self.ultimo_bloqueio = diagnostico
                return recusa

        entrada = {
            "contexto": montar_contexto(persona, perfil),
            "pergunta": pergunta,
        }
        if historico:
            entrada["historico"] = historico

        aceita = _ACEITA_RACIOCINIO.get(self.modelo)

        if aceita is not False:
            try:
                saida = (self._chain(True).invoke(entrada) or "").strip()
                if saida:
                    _ACEITA_RACIOCINIO.setdefault(self.modelo, True)
                    return self._pos_check(saida)
                _registrar(self.modelo, "chain: vazia com raciocinio")
            except Exception as e:
                _registrar(self.modelo, f"chain: erro com raciocinio: {type(e).__name__}")

        saida = (self._chain(False).invoke(entrada) or "").strip()
        if saida:
            _ACEITA_RACIOCINIO[self.modelo] = False
        return self._pos_check(saida)

    def _pos_check(self, saida: str) -> str:
        """Rede de segurança para o que o pré-check liberou e escorregou."""
        if not self.guardrails or not saida:
            return saida
        from src.guardrails import avaliar_saida
        aprovado, motivo = avaliar_saida(saida)
        if aprovado:
            return saida
        self.ultimo_bloqueio = {"camada": "pos_check", "categoria": motivo}
        return ("Não posso detalhar esse ponto por envolver instalação elétrica "
                "ou interpretação legal. Procure um profissional habilitado; "
                "posso ajudar com recarga, consumo e uso dos carregadores.")


def resumo_versao(versao: str = VERSAO_PADRAO) -> dict:
    """Linha da tabela de versões do §6."""
    texto = carregar_prompt(versao)
    return {
        "versao": versao,
        "arquivo": f"prompts/system_prompt_{versao}.md",
        "caracteres": len(texto),
        "tokens": contar_tokens(texto),
    }


if __name__ == "__main__":
    print(resumo_versao())
    chat = ChargeOpsChain()
    perfil = {"car_model": "BYD Dolphin", "battery_kwh": "44.9", "charger_kw": "7.4"}
    for p in ["Quanto tempo leva para carregar de 20% a 100%?",
              "Posso ligar o carregador direto no quadro? Qual bitola de cabo?",
              "Me indica um filme?"]:
        print(f"\n> {p}\n{chat.responder(p, 'morador', perfil)}")