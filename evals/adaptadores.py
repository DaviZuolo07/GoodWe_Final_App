"""
Adaptadores — a peça que torna a comparação honesta.

O runner conhece só esta interface:

    adaptador.nome
    adaptador.responder(pergunta, persona, perfil) -> str
    adaptador.prompt_renderizado(pergunta, persona, perfil) -> str

Ele não sabe se está falando com o chatbot manual da Sprint 2 ou com a chain
LCEL. Um único laço, uma única medição de tempo, uma única contagem de tokens.
A ÚNICA coisa que muda entre as colunas "antes" e "depois" é o que está dentro
do `responder`. É isso que transforma a tabela do §8 numa evidência.
"""

import os
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


# ===========================================================================
# LEGADO — a coluna "antes"
# ===========================================================================

class _RequestsComAuth:
    """
    Substituto do módulo `requests` DENTRO do módulo do legado.

    O PROBLEMA: `ai/services/llm_provider.py` faz

        requests.post(self.api_url, json=payload, timeout=180)

    sem nenhum cabeçalho. Isso funcionava na Sprint 2 porque o alvo era um
    Ollama local já autenticado (`gpt-oss:120b-cloud` em localhost:11434).
    Falando direto com a ollama.com, a mesma chamada leva 401.

    A TENTAÇÃO: abrir o llm_provider.py e acrescentar o header. Isso destrói o
    grupo de controle. A partir do momento em que o legado é editado, ele deixa
    de ser "a versão das Sprints 1/2" e a tabela antes/depois vira ficção.

    A SOLUÇÃO: trocar o objeto `requests` que o módulo legado enxerga, em tempo
    de execução. O arquivo em disco continua byte a byte idêntico. O que muda é
    só o transporte da credencial — infraestrutura, não comportamento. Montagem
    do prompt, ordem das mensagens, parâmetros do modelo: tudo intacto, e é
    exatamente isso que o eval está medindo.
    """

    def __init__(self, chave: str):
        self._chave = chave

    def post(self, url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        if self._chave:
            headers["Authorization"] = f"Bearer {self._chave}"
        return requests.post(url, headers=headers, **kwargs)

    def __getattr__(self, nome):
        return getattr(requests, nome)


class AdaptadorLegado:
    """
    Versão manual das Sprints 1/2 — a coluna "antes" da tabela obrigatória.

    NOTA DE HONESTIDADE PARA O RELATÓRIO: o legado não define temperature,
    top_p nem think, então roda com os padrões do Ollama (temperatura ~0.8). O
    LCEL usa 0.2 com seed fixa. Essa diferença NÃO é um truque para inflar o
    ganho: é literalmente uma das coisas que o refactory trouxe — controle de
    parâmetros. Mas precisa estar escrito no relatório, senão a comparação
    parece manipulada.
    """

    nome = "legado"

    def __init__(self, model: str | None = None):
        chave = (os.getenv("OLLAMA_API_KEY") or "").strip().strip('"').strip("'")
        host = (os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").strip().rstrip("/")

        # O legado lê OLLAMA_API_URL (endpoint completo), não OLLAMA_HOST.
        # Injetar a variável é configuração, não alteração de código.
        os.environ["OLLAMA_API_URL"] = f"{host}/api/chat"

        import ai.services.llm_provider as provider_legado
        from ai.prompts.prompt_loader import PromptLoader

        provider_legado.requests = _RequestsComAuth(chave)

        # BASE_PATH é relativo ("ai/prompts"): quebra se o runner for chamado
        # de outra pasta. Resolver para absoluto não muda o conteúdo lido.
        PromptLoader.BASE_PATH = RAIZ / "ai" / "prompts"

        self.modelo = (model or os.getenv("OLLAMA_MODEL") or "gpt-oss:120b").strip()
        os.environ["OLLAMA_MODEL"] = self.modelo
        self.nome = f"legado[{self.modelo}]"

        from ai.services.chat_service import ChatService
        self._ChatService = ChatService

    def _contexto_usuario(self, persona: str, perfil: dict | None) -> str:
        from ai.memory.user_profile_memory import UserProfileMemory
        dados = dict(perfil or {})
        dados.setdefault("persona", persona)
        return UserProfileMemory(dados).build_context()

    def prompt_renderizado(self, pergunta, persona="morador", perfil=None) -> str:
        """Reconstrói o texto que o legado envia — é o que a contagem mede."""
        from ai.context.goodwe_context import GOODWE_CONTEXT
        from ai.prompts.prompt_loader import PromptLoader
        return "\n".join([
            PromptLoader.load_system_prompt(),
            GOODWE_CONTEXT,
            self._contexto_usuario(persona, perfil),
            PromptLoader.load_few_shots(),
            pergunta,
        ])

    def responder(self, pergunta, persona="morador", perfil=None) -> str:
        # ChatService NOVO a cada caso. O legado tem ConversationMemory em RAM;
        # reaproveitar a instância deixaria o caso 5 contaminado pelos 4
        # anteriores. Os casos do eval são independentes por definição — e o
        # adaptador LCEL cru também não tem memória, então isolar aqui é o que
        # mantém os dois lados na mesma condição.
        servico = self._ChatService(
            system_context="",
            user_context=self._contexto_usuario(persona, perfil),
        )
        return servico.send_message(pergunta)


# ===========================================================================
# LCEL CRU — o piso da medição
# ===========================================================================

class AdaptadorLCELCru:
    """
    Chain LCEL mínima: prompt genérico, sem prompt versionado, sem guardrails,
    sem memória.

    Sem esta coluna, se o LCEL sair melhor que o legado não dá para saber se o
    ganho veio do LangChain ou do trabalho de prompt e guardrails:

        legado  ->  LCEL cru  ->  LCEL completo
                    (efeito do    (efeito do prompt
                     framework)    e dos guardrails)
    """

    nome = "lcel_cru"

    SISTEMA = (
        "Você é o ChargeOps AI, assistente da GoodWe especializado em recarga "
        "de veículos elétricos em condomínios residenciais. Responda em "
        "português do Brasil."
    )

    def __init__(self, model: str | None = None, papel: str = "principal"):
        from src.chain.llm import nome_do_modelo
        self.modelo = model or nome_do_modelo(papel)
        self.nome = f"lcel_cru[{self.modelo}]"

    def _perfil_texto(self, persona: str, perfil: dict | None) -> str:
        # O legado recebe o perfil do usuário; o LCEL cru precisa receber o
        # mesmo, ou casos como "quanto tempo leva no MEU carregador" ficariam
        # impossíveis de responder só num dos lados.
        dados = dict(perfil or {})
        dados.setdefault("persona", persona)
        linhas = [f"{k}: {v}" for k, v in dados.items() if v not in (None, "")]
        return "Dados do usuário atual:\n" + "\n".join(linhas)

    def prompt_renderizado(self, pergunta, persona="morador", perfil=None) -> str:
        return "\n".join([self.SISTEMA, self._perfil_texto(persona, perfil), pergunta])

    def responder(self, pergunta, persona="morador", perfil=None) -> str:
        from src.chain.execucao import invocar
        return invocar(
            [
                {"role": "system", "content": self.SISTEMA},
                {"role": "system", "content": self._perfil_texto(persona, perfil)},
                {"role": "user", "content": pergunta},
            ],
            model=self.modelo,
            perfil="redator",
            seed=42,
            # 1200 ainda cortou o S12-03 no meio (resposta de 1394 tokens).
            # O legado não define teto nenhum; comparar um lado truncado com um
            # lado inteiro produziria ganho falso. Aqui a folga é generosa de
            # propósito: a verbosidade do cru é um ACHADO a ser medido, não um
            # defeito a ser escondido com corte.
            num_predict=2200,
        )


# ===========================================================================
# LCEL COMPLETO — a coluna "depois"
# ===========================================================================

class AdaptadorLCEL:
    """
    Chain LCEL com prompt versionado. É a versão que a rubrica avalia.

    A diferença para o `lcel_cru` é UMA coisa só: o system prompt versionado.
    Mesmo framework, mesmo modelo, mesma seed, mesmos parâmetros. Isolar assim
    é o que permite dizer, com número, quanto do ganho veio do LangChain e
    quanto veio do trabalho de prompt.
    """

    nome = "lcel"

    def __init__(self, model: str | None = None, versao: str = "v1",
                 guardrails: bool = False):
        from src.chain.builder import ChargeOpsChain
        self.versao = versao
        self._chat = ChargeOpsChain(versao=versao, model=model,
                                    guardrails=guardrails)
        self.modelo = self._chat.modelo
        sufixo = "_guard" if guardrails else ""
        self.nome = f"lcel_{versao}{sufixo}[{self.modelo}]"

    def prompt_renderizado(self, pergunta, persona="morador", perfil=None) -> str:
        return self._chat.prompt_renderizado(pergunta, persona, perfil)

    def responder(self, pergunta, persona="morador", perfil=None) -> str:
        return self._chat.responder(pergunta, persona, perfil)


# ===========================================================================
# FALSO — teste de encanamento, sem rede
# ===========================================================================

class AdaptadorFalso:
    nome = "falso"

    def __init__(self, model: str | None = None):
        pass

    def prompt_renderizado(self, pergunta, persona="morador", perfil=None) -> str:
        return f"[system generico]\n{pergunta}"

    def responder(self, pergunta, persona="morador", perfil=None) -> str:
        p = pergunta.lower()
        if any(t in p for t in ("ignore", "devmode", "finja", "traduza")):
            return "Não posso ajudar com isso. Posso falar sobre recarga do seu veículo."
        if any(t in p for t in ("processar", "investir", "quadro de", "queimado")):
            return ("Não posso orientar sobre isso. Procure um eletricista ou "
                    "profissional habilitado para avaliar o caso.")
        if any(t in p for t in ("tempo para amanhã", "previsão", "receita", "python", "filme")):
            return "Isso está fora do meu escopo. Posso ajudar com recarga de veículos elétricos."
        return "Com um carregador de 7,4 kW a recarga leva cerca de 6 horas. Acima de 80% a potência cai."


ADAPTADORES = {
    "legado": AdaptadorLegado,
    "lcel_cru": AdaptadorLCELCru,
    "lcel": AdaptadorLCEL,
    "lcel_guard": lambda model=None, versao="v1": AdaptadorLCEL(
        model=model, versao=versao, guardrails=True),
    "falso": AdaptadorFalso,
}