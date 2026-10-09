"""
Chain RAG da Sprint 04 (Aula 06), composta em LCEL sobre os módulos de `src/rag/`.

    python -m src.chain.rag "Qual o grau de proteção do HCA G2?"
    python -m src.chain.rag --detalhes          # modo conversa, mostra fontes e scores

PIPELINE DE UM TURNO — a ordem é o acordo do CLAUDE.md §6 ("o retriever decide
primeiro"):

    pergunta ─► moderação (injection/jailbreak) ─┬─ bloqueada ─► resposta fixa
                                                 └─► emergência elétrica? ─► resposta fixa (193)
                                                 └─► retriever (k, limiar)
                                                       ├─ nenhum trecho ─► scope_validator:
                                                       │                    encaminhamento ou RECUSA literal
                                                       └─ trechos ─► prompt RAG | llm | parser
                                                                     ─► pós-processamento

Antes do RAG, o `scope_validator` rodava ANTES do modelo e recusava qualquer
pergunta com "lei", "artigo" ou "advogado" — inclusive as que a base passará a
responder (Lei SP 18.403, IT-41). Agora ele só decide quando o retriever não
achou nada: é a rede de segurança, não o porteiro.

A única exceção à ordem é a EMERGÊNCIA elétrica (fumaça, faísca, choque): ela
responde antes da busca, porque a resposta fixa manda desligar e ligar 193, e
nenhum trecho de manual recuperado por similaridade pode atrasar ou diluir isso.

PÓS-PROCESSAMENTO (determinístico, não depende do modelo obedecer):
  - recusa do modelo é normalizada para a string literal;
  - resposta sem citação recebe a do trecho mais similar (`citacao_adicionada`);
  - citação de documento/página que não foi recuperado é registrada
    (`citacoes_invalidas`) — é alucinação de fonte, e o eval conta;
  - vazamento de canário ou de tags troca a resposta pela recusa de injection;
  - número de instalação elétrica (bitola, disjuntor) vindo do MANUAL é mantido,
    com citação, e ganha o encaminhamento ao eletricista habilitado. O guardrail
    da Sprint 3 trocaria a resposta inteira por recusa, o que apagaria uma
    informação oficial e citada.
"""

from __future__ import annotations

import argparse
import sys

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (Runnable, RunnableBranch, RunnableConfig, RunnableLambda,
                                      RunnablePassthrough)

from src.chain.builder import limpar_saida
from src.chain.llm import descrever as descrever_llm
from src.chain.llm import get_llm_robusto
from src.chain.prompts import CANARIO
from src.guardrails.moderation import moderar, normalizar
from src.guardrails.scope_validator import EMERGENCIA, RESPOSTAS, validar_escopo, validar_saida
from src.rag import chunking, embeddings, prompt_rag
from src.rag.prompt_rag import RECUSA
from src.rag.retriever import Recuperador
from src.schemas.resultados import RespostaRAG

PERFIL_LLM = "rag"

AVISO_ELETRICO = ("A instalação e qualquer ajuste elétrico devem ser feitos por eletricista "
                  "habilitado, com ART ou TRT.")


def montar_chain_resposta(versao: str, llm) -> Runnable:
    """prompt RAG | llm | parser — a parte da chain que vai ao modelo."""
    return (prompt_rag.montar_template(versao)
            | llm
            | StrOutputParser()
            | RunnableLambda(limpar_saida, name="limpar_saida"))


class ChatbotRAG:
    def __init__(
        self,
        versao_prompt: str = prompt_rag.VERSAO_PADRAO,
        papel: str = "principal",
        model: str | None = None,
        recuperador: Recuperador | None = None,
        llm: BaseChatModel | Runnable | None = None,
        guardrails: bool = True,
    ):
        self.versao = versao_prompt
        self.papel = papel
        self.model = model
        self.guardrails = guardrails
        # Injetáveis: os testes offline passam retriever e LLM falsos.
        self.recuperador = recuperador or Recuperador()
        self.llm = llm or get_llm_robusto(PERFIL_LLM, papel=papel, model=model)
        self.chain_resposta = montar_chain_resposta(versao_prompt, self.llm)
        self.pipeline = self._montar_pipeline()

    # ------------------------------------------------------------------ #
    def _montar_pipeline(self) -> Runnable:
        entrada = RunnableLambda(self._etapa_guardrails, name="guardrails_entrada")
        fixa = RunnableLambda(self._etapa_resposta_fixa, name="resposta_fixa")
        sem_contexto = RunnableLambda(self._etapa_sem_contexto, name="sem_contexto")
        rag = RunnableLambda(self._etapa_rag, name="resposta_rag")
        busca = RunnablePassthrough.assign(trechos=RunnableLambda(self._etapa_busca, name="retriever"))
        return entrada | RunnableBranch(
            (lambda x: x["guardrail"] is not None, fixa),
            busca | RunnableBranch((lambda x: not x["trechos"]["usados"], sem_contexto), rag),
        )

    # -- etapa 1: moderação e emergência ---------------------------------
    def _etapa_guardrails(self, x: dict) -> dict:
        if not self.guardrails:
            return {**x, "guardrail": None}
        m = moderar(x["pergunta"])
        if m.bloqueado:
            return {**x, "guardrail": {"rota": "bloqueio_moderacao", "categoria": m.categoria,
                                       "resposta": m.resposta}}
        if EMERGENCIA.search(normalizar(x["pergunta"])):
            return {**x, "guardrail": {"rota": "recusa_escopo", "categoria": "emergencia_eletrica",
                                       "resposta": RESPOSTAS["emergencia_eletrica"]}}
        return {**x, "guardrail": None}

    def _etapa_resposta_fixa(self, x: dict) -> RespostaRAG:
        g = x["guardrail"]
        return RespostaRAG(texto=g["resposta"], rota=g["rota"], categoria_guardrail=g["categoria"])

    # -- etapa 2: retriever ----------------------------------------------
    def _etapa_busca(self, x: dict) -> dict:
        todos = self.recuperador.buscar_tudo(x["pergunta"])
        usados = [t for t in todos if t.score >= self.recuperador.limiar]
        return {"usados": usados, "descartados": [t for t in todos if t not in usados]}

    # -- etapa 3a: nada acima do limiar -> scope_validator decide ----------
    def _etapa_sem_contexto(self, x: dict) -> RespostaRAG:
        descartados = [t.resumo() for t in x["trechos"]["descartados"]]
        if self.guardrails:
            # modelos_base=None: a especificação agora vem da base vetorizada, não
            # do prompts/base_produtos.json (que tem modelos que o datasheet não lista).
            e = validar_escopo(x["pergunta"], modelos_base=None)
            if not e.permitido:
                return RespostaRAG(texto=e.resposta, rota="recusa_escopo", categoria_guardrail=e.categoria,
                                   descartados=descartados)
        return RespostaRAG(texto=RECUSA, rota="sem_contexto", descartados=descartados)

    # -- etapa 3b: resposta com contexto ----------------------------------
    def _etapa_rag(self, x: dict, config: RunnableConfig) -> RespostaRAG:
        usados = x["trechos"]["usados"]
        texto = self.chain_resposta.invoke(
            {"pergunta": x["pergunta"], "contexto": prompt_rag.formatar_contexto(usados)}, config=config)
        return self._pos_processar(texto, usados, x["trechos"]["descartados"])

    def _pos_processar(self, texto: str, usados, descartados) -> RespostaRAG:
        base = {"fontes": [t.resumo() for t in usados], "descartados": [t.resumo() for t in descartados],
                "chamadas_llm": 1}

        corrigido, motivo = (validar_saida(texto, CANARIO) if self.guardrails else (texto, None))
        if motivo and motivo != "instrucao_eletrica_na_saida":
            return RespostaRAG(texto=corrigido, rota="rag", saida_corrigida_por_guardrail=motivo, **base)

        if prompt_rag.eh_recusa(texto):
            return RespostaRAG(texto=RECUSA, rota="recusa_llm", **base)

        recuperados = {(t.documento, t.pagina) for t in usados}
        citadas = prompt_rag.extrair_citacoes(texto)
        invalidas = [prompt_rag.citacao(d, p) for d, p in citadas if (d, p) not in recuperados]
        adicionada = not citadas
        if adicionada:
            texto = f"{texto.rstrip()} {usados[0].citacao}"
        if motivo == "instrucao_eletrica_na_saida":
            texto = f"{texto.rstrip()} {AVISO_ELETRICO}"

        return RespostaRAG(
            texto=texto, rota="rag",
            citacoes=[prompt_rag.citacao(d, p) for d, p in prompt_rag.extrair_citacoes(texto)],
            citacao_adicionada=adicionada, citacoes_invalidas=invalidas,
            saida_corrigida_por_guardrail="aviso_eletricista" if motivo else None, **base)

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def responder(self, pergunta: str) -> RespostaRAG:
        uso = UsageMetadataCallbackHandler()
        r: RespostaRAG = self.pipeline.invoke(
            {"pergunta": pergunta}, config={"callbacks": [uso], "run_name": f"rag_{self.versao}"})
        entrada = sum(u.get("input_tokens", 0) for u in uso.usage_metadata.values())
        saida = sum(u.get("output_tokens", 0) for u in uso.usage_metadata.values())
        return r.model_copy(update={"tokens_servidor_entrada": entrada, "tokens_servidor_saida": saida})

    def descrever(self) -> dict:
        """Todos os parâmetros do experimento juntos — cabeçalho de todo eval (bloco C)."""
        return {
            "prompt_rag": prompt_rag.descrever(self.versao),
            "llm": descrever_llm(perfil=PERFIL_LLM, papel=self.papel, model=self.model),
            "retriever": self.recuperador.descrever(),
            "embeddings": embeddings.descrever(),
            "chunking": chunking.descrever(),
        }


def _imprimir(r: RespostaRAG, detalhes: bool) -> None:
    print(f"\n{r.texto}\n")
    if not detalhes:
        return
    print(f"  rota: {r.rota}" + (f" ({r.categoria_guardrail})" if r.categoria_guardrail else ""))
    for f in r.fontes:
        print(f"  [usado {f['score']:.3f}] {f['documento']}, página {f['pagina']}")
    for f in r.descartados:
        print(f"  [abaixo {f['score']:.3f}] {f['documento']}, página {f['pagina']}")
    if r.citacao_adicionada:
        print("  ! o modelo não citou; citação anexada pela chain")
    if r.citacoes_invalidas:
        print(f"  ! citações que não vieram do retriever: {r.citacoes_invalidas}")
    if r.saida_corrigida_por_guardrail:
        print(f"  ! saída ajustada: {r.saida_corrigida_por_guardrail}")
    print(f"  tokens servidor: {r.tokens_servidor_entrada} in / {r.tokens_servidor_saida} out\n")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Chatbot RAG GoodWe ChargeOps (Sprint 04)")
    ap.add_argument("pergunta", nargs="*", help="pergunta única; sem ela, abre o modo conversa")
    ap.add_argument("--prompt", default=prompt_rag.VERSAO_PADRAO, choices=list(prompt_rag.VERSOES))
    ap.add_argument("--modelo", default=None)
    ap.add_argument("--detalhes", action="store_true", help="mostra rota, fontes e scores")
    a = ap.parse_args()

    bot = ChatbotRAG(versao_prompt=a.prompt, model=a.modelo)
    if a.pergunta:
        _imprimir(bot.responder(" ".join(a.pergunta)), detalhes=True)
        return

    print(f"ChargeOps RAG — prompt {a.prompt}. /sair para encerrar.")
    while True:
        try:
            pergunta = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta in ("/sair", "sair", "exit"):
            break
        if pergunta:
            _imprimir(bot.responder(pergunta), a.detalhes)


if __name__ == "__main__":
    main()
