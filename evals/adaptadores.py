"""
Adaptadores — a peça que torna a comparação honesta.

O runner não sabe se está falando com o chatbot manual da Sprint 2 ou com a
chain LCEL da Sprint 3. Ele conhece só esta interface:

    adaptador.nome          -> string para o relatório
    adaptador.responder(pergunta, persona) -> str

Por que isso importa para a nota: o §8 exige que o MESMO eval set rode nos dois
lados. Se cada lado tivesse seu próprio script de execução, qualquer diferença
acidental entre os dois scripts (um trunca a pergunta, outro não; um usa
temperatura diferente) viraria "ganho do refactory" no relatório. Seria um
ganho falso.

Com o adaptador, existe um único caminho de execução, uma única medição de
tempo e uma única contagem de tokens. A ÚNICA coisa que muda entre as colunas
"antes" e "depois" é o que está dentro do `responder`. É isso que transforma a
tabela numa evidência em vez de duas listas soltas.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


class AdaptadorLCELCru:
    """
    Chain LCEL mínima: prompt genérico, sem prompt versionado, sem guardrails,
    sem memória.

    Serve de PISO da medição. Sem ele, se o LCEL sair melhor que o legado, não
    dá para saber se o ganho veio do LangChain ou do trabalho de prompt e
    guardrails que virá nos passos 3 a 7. Este adaptador separa as duas coisas:

        legado  ->  LCEL cru  ->  LCEL completo
                    (efeito       (efeito do prompt
                     do framework)  e dos guardrails)

    Três colunas contam uma história que duas não contam.
    """

    nome = "lcel_cru"

    def __init__(self, papel: str = "principal", model: str | None = None):
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        from src.chain.llm import get_llm, nome_do_modelo

        self.modelo = model or nome_do_modelo(papel)
        self.nome = f"lcel_cru[{self.modelo}]"

        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Você é o ChargeOps AI, assistente da GoodWe especializado em "
             "recarga de veículos elétricos em condomínios residenciais. "
             "Responda em português do Brasil."),
            ("human", "{pergunta}"),
        ])

        self.chain = (
            self.prompt
            | get_llm(perfil="redator", model=self.modelo, seed=42)
            | StrOutputParser()
        )

    def prompt_renderizado(self, pergunta: str, persona: str = "morador") -> str:
        """Texto exato enviado ao modelo — é o que a contagem de tokens mede."""
        msgs = self.prompt.format_messages(pergunta=pergunta)
        return "\n".join(str(m.content) for m in msgs)

    def responder(self, pergunta: str, persona: str = "morador") -> str:
        return self.chain.invoke({"pergunta": pergunta})


class AdaptadorLegado:
    """
    Versão manual das Sprints 1/2 — a coluna "antes" da tabela obrigatória.

    NÃO IMPLEMENTADO AINDA. Falta o código de `ai/` para saber a assinatura
    real. Assim que os arquivos chegarem, este adaptador vira ~20 linhas.

    REGRA INEGOCIÁVEL: este adaptador CHAMA o código de `ai/` sem alterar uma
    vírgula dele. Se for preciso mexer no legado para o eval rodar, o legado
    deixa de ser grupo de controle e a comparação perde validade.
    """

    nome = "legado"

    def __init__(self, persona_padrao: str = "morador"):
        self.persona_padrao = persona_padrao
        # TODO(passo 2): quando chegarem os arquivos de ai/
        #   from ai.services.chat_service import ChatService
        #   self.servico = ChatService(...)
        raise NotImplementedError(
            "AdaptadorLegado precisa dos arquivos de ai/:\n"
            "  ai/services/chat_service.py\n"
            "  ai/services/llm_provider.py\n"
            "  ai/agents/chargeops_agent.py\n"
            "  ai/prompts/system_prompt.txt"
        )

    def prompt_renderizado(self, pergunta: str, persona: str = "morador") -> str:
        raise NotImplementedError

    def responder(self, pergunta: str, persona: str = "morador") -> str:
        raise NotImplementedError


class AdaptadorFalso:
    """Respostas fixas, sem rede. Existe para testar o runner sem gastar cota."""

    nome = "falso"

    def prompt_renderizado(self, pergunta: str, persona: str = "morador") -> str:
        return f"[system generico]\n{pergunta}"

    def responder(self, pergunta: str, persona: str = "morador") -> str:
        p = pergunta.lower()
        if any(t in p for t in ("ignore", "devmode", "finja", "síndico", "sindico")):
            return "Não posso ajudar com isso. Posso falar sobre recarga do seu veículo."
        if any(t in p for t in ("processar", "investir", "quadro de força", "queimado")):
            return ("Não posso orientar sobre isso. Procure um profissional habilitado "
                    "para avaliar o caso.")
        if any(t in p for t in ("tempo", "previsão", "receita", "python")):
            return "Isso está fora do meu escopo. Posso ajudar com recarga de veículos elétricos."
        return "Com um carregador de 7,4 kW a recarga leva cerca de 6 horas. Acima de 80% a potência cai."


ADAPTADORES = {
    "lcel_cru": AdaptadorLCELCru,
    "legado": AdaptadorLegado,
    "falso": AdaptadorFalso,
}
