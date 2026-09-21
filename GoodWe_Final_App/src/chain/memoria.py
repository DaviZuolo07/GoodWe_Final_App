"""
Memória por sessão com limite de tokens (Aula 02).

O contrato pede DUAS peças que, no LangChain 1.x, não conversam sozinhas:

  RunnableWithMessageHistory       espera um BaseChatMessageHistory por sessão
  ConversationTokenBufferMemory    é uma "memory" do mundo legacy (save_context)

`HistoricoComLimiteDeTokens` é o adaptador: por fora ele é um
BaseChatMessageHistory (o que o RunnableWithMessageHistory aceita); por dentro
cada par pergunta/resposta é gravado via `ConversationTokenBufferMemory.save_context`,
que é quem aplica a janela deslizante e descarta as mensagens mais antigas
quando o `max_token_limit` estoura. Nenhuma lógica de poda foi reescrita —
usamos a da própria classe exigida pelo escopo.

POLÍTICA DE RESUMO (o que acontece com o que sai da janela)
-----------------------------------------------------------
Uma janela deslizante pura esquece "minha bateria é de 60 kWh" dito no turno 1
— e aí o turno 8 pede o dado de novo, ou pior, o modelo chuta. Um resumo
gerado por LLM (ConversationSummaryMemory) resolveria, mas custa uma chamada
extra por turno e pode alucinar número ao resumir (Aula 02, FAQ).

Escolha: resumo ESTRUTURADO. Os fatos numéricos da conversa já são extraídos
e validados pelo schema Pydantic (`ConsultaRecarga`) a cada turno relevante;
eles ficam em `EstadoSessao.fatos` e entram no prompt como <fatos_da_sessao>,
independentemente da janela. Resultado: custo de tokens com teto fixo (pela
janela) + fatos críticos que nunca se perdem + zero chamada extra de resumo.

O limite padrão (MEMORIA_MAX_TOKENS=1200) está justificado em
docs/relatorio_modelos.md, a partir do tamanho medido das respostas.
"""

from __future__ import annotations

import os
import threading
import warnings
from dataclasses import dataclass, field

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

with warnings.catch_warnings():
    # A classe é marcada como deprecated no LangChain 1.x (sugere LangGraph).
    # O escopo da Sprint 03 exige ESTA classe; o aviso é registrado no
    # relatório em vez de poluir a saída de cada execução.
    warnings.simplefilter("ignore")
    from langchain_classic.memory import ConversationTokenBufferMemory

from src.chain import tokens

MAX_TOKENS_PADRAO = int(os.getenv("MEMORIA_MAX_TOKENS", "1200"))


class HistoricoComLimiteDeTokens(BaseChatMessageHistory):
    """BaseChatMessageHistory cuja poda é feita pela ConversationTokenBufferMemory."""

    def __init__(self, llm_contador: BaseLanguageModel, max_token_limit: int = MAX_TOKENS_PADRAO):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.memoria = ConversationTokenBufferMemory(
                llm=llm_contador,
                max_token_limit=max_token_limit,
                memory_key="history",
                return_messages=True,
            )
        self.mensagens_descartadas: list[BaseMessage] = []
        self.eventos_de_poda = 0
        self._pendente: HumanMessage | None = None

    # -- interface BaseChatMessageHistory ---------------------------------
    @property
    def messages(self) -> list[BaseMessage]:  # type: ignore[override]
        return list(self.memoria.chat_memory.messages)

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """
        O RunnableWithMessageHistory entrega [HumanMessage, AIMessage] ao fim
        de cada turno. Cada par vira um `save_context`, que poda sozinho.
        """
        for m in messages:
            if isinstance(m, HumanMessage):
                self._pendente = m
            elif isinstance(m, AIMessage):
                entrada = self._pendente.content if self._pendente else ""
                self._salvar(str(entrada), str(m.content))
                self._pendente = None

    def clear(self) -> None:
        self.memoria.clear()
        self._pendente = None

    # -- internos ----------------------------------------------------------
    def _salvar(self, entrada: str, saida: str) -> None:
        antes = list(self.memoria.chat_memory.messages)
        self.memoria.save_context({"input": entrada}, {"output": saida})
        depois = self.memoria.chat_memory.messages
        n_descartadas = len(antes) + 2 - len(depois)
        if n_descartadas > 0:
            self.eventos_de_poda += 1
            combinadas = antes + [HumanMessage(entrada), AIMessage(saida)]
            self.mensagens_descartadas.extend(combinadas[:n_descartadas])

    # -- inspeção (para a demonstração e o relatório) ----------------------
    @property
    def max_token_limit(self) -> int:
        return self.memoria.max_token_limit

    def tokens_na_janela(self) -> int:
        return self.memoria.llm.get_num_tokens_from_messages(self.messages)

    def load_memory_variables(self) -> dict:
        """Mesma inspeção ensinada na Aula 02."""
        return self.memoria.load_memory_variables({})


@dataclass
class EstadoSessao:
    historico: HistoricoComLimiteDeTokens
    fatos: dict = field(default_factory=dict)   # resumo estruturado (ConsultaRecarga.fatos())
    turnos: int = 0


class RepositorioSessoes:
    """Armazena uma EstadoSessao por session_id (multiusuário, thread-safe)."""

    def __init__(self, llm_contador: BaseLanguageModel, max_token_limit: int = MAX_TOKENS_PADRAO):
        self._llm_contador = llm_contador
        self._limite = max_token_limit
        self._sessoes: dict[str, EstadoSessao] = {}
        self._trava = threading.Lock()

    def obter(self, session_id: str) -> EstadoSessao:
        with self._trava:
            if session_id not in self._sessoes:
                self._sessoes[session_id] = EstadoSessao(
                    HistoricoComLimiteDeTokens(self._llm_contador, self._limite))
            return self._sessoes[session_id]

    def historico(self, session_id: str) -> BaseChatMessageHistory:
        """`get_session_history` do RunnableWithMessageHistory."""
        return self.obter(session_id).historico

    def limpar(self, session_id: str) -> None:
        with self._trava:
            self._sessoes.pop(session_id, None)


def renderizar_fatos(fatos: dict) -> str:
    if not fatos:
        return "nenhum dado informado nesta sessão"
    rotulos = {
        "capacidade_bateria_kwh": ("capacidade da bateria", "kWh"),
        "soc_atual_pct": ("nível atual da bateria", "%"),
        "soc_alvo_pct": ("nível desejado", "%"),
        "potencia_carregador_kw": ("potência do carregador", "kW"),
        "potencia_max_ac_veiculo_kw": ("potência máxima AC do veículo", "kW"),
        "tarifa_kwh_brl": ("tarifa informada", "R$/kWh"),
        "energia_entregue_kwh": ("energia já entregue", "kWh"),
        "estado_carregador": ("estado do carregador informado", ""),
        "tipo_corrente": ("tipo de recarga", ""),
        "modelo_carregador": ("modelo de carregador citado", ""),
    }
    linhas = []
    for chave, valor in fatos.items():
        rotulo, unidade = rotulos.get(chave, (chave, ""))
        v = f"{valor:g}".replace(".", ",") if isinstance(valor, float) else str(valor)
        linhas.append(f"- {rotulo}: {v} {unidade}".rstrip())
    return "\n".join(linhas)


def contar_tokens_mensagens(msgs: list[BaseMessage]) -> int:
    return tokens.contar_mensagens(msgs)
