"""
Chain RAG da Sprint 04 (Aula 06), composta em LCEL sobre os módulos de `src/rag/`.

    python -m src.chain.rag "Qual o grau de proteção do HCA G2?"
    python -m src.chain.rag --detalhes          # modo conversa, mostra fontes e scores

PIPELINE DE UM TURNO — a ordem é o acordo do CLAUDE.md §6 ("o retriever decide
primeiro"):

    pergunta ─► moderação (injection/jailbreak) ─┬─ bloqueada ─► resposta fixa
                                                 └─► emergência elétrica? ─► resposta fixa (193)
                                                 └─► retriever (k, limiar, filtro de injection)
                                                       ├─ nenhum trecho ─► sem resposta na base
                                                       └─ trechos ─► prompt RAG | llm | parser
                                                                     ─► pós-processamento
                                                                        (recusa do modelo ─► sem resposta na base)

    SEM RESPOSTA NA BASE — um critério só, nos dois caminhos acima:
        jurídico, financeiro ou segurança elétrica ─► encaminhamento a profissional habilitado
        qualquer outro caso                         ─► RECUSA literal (invariante 1 do CLAUDE.md)

"Sem resposta na base" acontece de dois jeitos: nenhum trecho passa do limiar,
ou passa mas o modelo recusa. O segundo é o mais comum em pergunta jurídica:
"posso processar o síndico por não deixar instalar o carregador?" cita
"carregador" e "síndico", traz trechos do manual com score 0,75 e o modelo
corretamente recusa. Sem tratar a recusa do modelo como "sem resposta", o
encaminhamento ao advogado (§6 do enunciado) se perdia.

Jurídico é checado ANTES do `validar_escopo`, de propósito: a pergunta acima
também casa com a regra de segurança elétrica ("instalar o carregador"), que
o `validar_escopo` testa primeiro — e o morador receberia "chame um
eletricista" para uma dúvida sobre direito.

Antes do RAG, o `scope_validator` rodava ANTES do modelo e recusava qualquer
pergunta com "lei", "artigo" ou "advogado" — inclusive as que a base passará a
responder (Lei SP 18.403, IT-41). Agora ele só decide quando o retriever não
achou nada: é a rede de segurança, não o porteiro.

A única exceção à ordem é a EMERGÊNCIA elétrica (fumaça, faísca, choque): ela
responde antes da busca, porque a resposta fixa manda desligar e ligar 193, e
nenhum trecho de manual recuperado por similaridade pode atrasar ou diluir isso.

APRESENTAÇÃO ("do que se trata esse chatbot?", "oi", "o que você faz?") também
responde antes da busca, com texto fixo. Sem isso, a primeira coisa que um
usuário novo digita recebia "Não encontrei essa informação nos documentos" —
correto pela regra, inútil na prática (teste na interface, 10/10/2026). O texto
fixo descreve o assistente e a base, e não contém nenhuma especificação de
produto, então não fere o grounding (invariante 3). O padrão casa a pergunta
INTEIRA (`fullmatch`): "o que você sabe sobre a potência do GW22K?" vai para o
retriever, não para a apresentação.

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
import re
import sys

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (Runnable, RunnableBranch, RunnableConfig, RunnableLambda,
                                      RunnablePassthrough)

from src.chain.builder import limpar_saida
from src.chain.llm import descrever as descrever_llm
from src.chain.llm import get_llm, get_llm_robusto
from src.chain.prompts import CANARIO
from src.guardrails.moderation import moderar, normalizar
from src.guardrails.scope_validator import (EMERGENCIA, JURIDICO, RESPOSTAS, validar_escopo,
                                            validar_saida)
from src.rag import chunking, embeddings, prompt_rag
from src.rag.prompt_rag import RECUSA
from src.rag.retriever import Recuperador
from src.schemas.resultados import RespostaRAG

PERFIL_LLM = "rag"

# Sem resposta na base, estas categorias do scope_validator ganham o
# encaminhamento a profissional habilitado; as demais viram a RECUSA literal.
ENCAMINHAMENTO_PROFISSIONAL = ("juridico", "financeiro", "seguranca_eletrica")

APRESENTACAO = (
    "Sou o ChargeOps, assistente da GoodWe para recarga de veículos elétricos no condomínio. "
    "Respondo dúvidas sobre o carregador GoodWe HCA G2 (uso, luzes, falhas, especificações e "
    "manutenção), as regras de uso das vagas de recarga e a tarifa cobrada, sempre com base nos "
    "documentos indexados: manual do usuário, datasheet e resumo Modbus do HCA G2, FAQ de recarga, "
    "regimento e tabela tarifária do condomínio de demonstração. Toda resposta traz a fonte, com "
    "documento e página; se a informação não estiver nos documentos, eu digo que não encontrei. "
    "Experimente: \"Qual a potência do GW22K-HCA-20?\" ou \"Quanto custa uma recarga de 30 kWh?\"")
# Texto normalizado (minúsculo, sem acento). Casa a pergunta inteira, nunca um pedaço.
_RE_APRESENTACAO = re.compile(
    r"(oi+|ola|ola tudo bem|bom dia|boa tarde|boa noite|e ai|hello|hi|hey|ajuda|help|menu|inicio)"
    r"|(do que|sobre o que) (se trata|e|fala) (esse|este|o|a|essa|esta) "
    r"(chat|chatbot|bot|assistente|sistema|ferramenta|aplicativo|app|projeto)"
    r"|(o que|quem) (e|sao) (voce|vc|o chargeops|esse (chat|chatbot|bot|assistente))"
    r"|o que (voce|vc|o chargeops) (faz|pode fazer|sabe fazer|responde)"
    r"|(o que|sobre o que) (eu )?(posso|da para|consigo) (te )?perguntar"
    r"|(como|para que) (voce|vc|esse (chat|chatbot|bot|assistente)) (funciona|serve)"
)


def eh_apresentacao(pergunta: str) -> bool:
    t = re.sub(r"[^\w\s]", " ", normalizar(pergunta))
    return bool(_RE_APRESENTACAO.fullmatch(" ".join(t.split())))


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
        # Streaming (interface): o fallback de `get_llm_robusto` acumula a resposta
        # inteira antes de devolver (a checagem de conteúdo vazio precisa do texto
        # completo), então a tela ficaria parada. A interface usa o LLM simples e
        # cai na chain robusta só se o stream vier vazio. Mesmo perfil "rag".
        llm_stream = llm or get_llm(PERFIL_LLM, papel=papel, model=model)
        self.chain_stream = prompt_rag.montar_template(versao_prompt) | llm_stream | StrOutputParser()
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
        if eh_apresentacao(x["pergunta"]):
            return {**x, "guardrail": {"rota": "apresentacao", "categoria": None, "resposta": APRESENTACAO}}
        return {**x, "guardrail": None}

    def _etapa_resposta_fixa(self, x: dict) -> RespostaRAG:
        g = x["guardrail"]
        return RespostaRAG(texto=g["resposta"], rota=g["rota"], categoria_guardrail=g["categoria"])

    # -- etapa 2: retriever ----------------------------------------------
    def _etapa_busca(self, x: dict) -> dict:
        todos = self.recuperador.buscar_tudo(x["pergunta"])
        acima = [t for t in todos if t.score >= self.recuperador.limiar]
        # Injection via documento: o trecho que dá ordem ao modelo não chega a ele.
        suspeitos = {t.chunk_id: motivo for t in acima if (motivo := prompt_rag.trecho_suspeito(t.texto))}
        usados = [t for t in acima if t.chunk_id not in suspeitos]
        injecao = [{**t.resumo(), "motivo": suspeitos[t.chunk_id]} for t in acima if t.chunk_id in suspeitos]
        return {"usados": usados, "descartados": [t for t in todos if t not in acima], "injecao": injecao}

    # -- sem resposta na base -> encaminhamento ou RECUSA literal ----------
    def _encaminhamento(self, pergunta: str) -> tuple[str, str] | None:
        """(categoria, resposta fixa) quando a pergunta pede profissional habilitado."""
        if not self.guardrails:
            return None
        if JURIDICO.search(normalizar(pergunta)):
            return "juridico", RESPOSTAS["juridico"]
        # modelos_base=None: a especificação agora vem da base vetorizada, não
        # do prompts/base_produtos.json (que tem modelos que o datasheet não lista).
        e = validar_escopo(pergunta, modelos_base=None)
        if not e.permitido and e.categoria in ENCAMINHAMENTO_PROFISSIONAL:
            return e.categoria, e.resposta
        return None

    # -- etapa 3a: nada acima do limiar ------------------------------------
    def _etapa_sem_contexto(self, x: dict) -> RespostaRAG:
        base = {"descartados": [t.resumo() for t in x["trechos"]["descartados"]],
                "descartados_por_injecao": x["trechos"]["injecao"]}
        encaminhar = self._encaminhamento(x["pergunta"])
        if encaminhar:
            return RespostaRAG(texto=encaminhar[1], rota="recusa_escopo", categoria_guardrail=encaminhar[0], **base)
        return RespostaRAG(texto=RECUSA, rota="sem_contexto", **base)

    # -- etapa 3b: resposta com contexto ----------------------------------
    def _etapa_rag(self, x: dict, config: RunnableConfig) -> RespostaRAG:
        usados = x["trechos"]["usados"]
        texto = self.chain_resposta.invoke(
            {"pergunta": x["pergunta"], "contexto": prompt_rag.formatar_contexto(usados)}, config=config)
        return self._pos_processar(texto, usados, x["trechos"]["descartados"], x["pergunta"],
                                   x["trechos"].get("injecao", []))

    def _pos_processar(self, texto: str, usados, descartados, pergunta: str = "",
                       injecao: list[dict] | None = None) -> RespostaRAG:
        base = {"fontes": [t.resumo() for t in usados], "descartados": [t.resumo() for t in descartados],
                "descartados_por_injecao": injecao or [], "chamadas_llm": 1}

        corrigido, motivo = (validar_saida(texto, CANARIO) if self.guardrails else (texto, None))
        if motivo and motivo != "instrucao_eletrica_na_saida":
            return RespostaRAG(texto=corrigido, rota="rag", saida_corrigida_por_guardrail=motivo, **base)

        if prompt_rag.eh_recusa(texto):
            encaminhar = self._encaminhamento(pergunta)
            if encaminhar:
                return RespostaRAG(texto=encaminhar[1], rota="recusa_escopo",
                                   categoria_guardrail=encaminhar[0], **base)
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

    def responder_stream(self, pergunta: str):
        """
        Mesmo pipeline do `responder`, com a parte do modelo em streaming (Aula 08).

        Gera ("parcial", texto_acumulado) enquanto o modelo escreve e termina com
        ("final", RespostaRAG). Guardrails, retriever e pós-processamento são os
        mesmos métodos do `responder`, na mesma ordem: a tela mostra o texto
        parcial cru, e o texto final (recusa normalizada, citação conferida) o
        substitui. Por isso a interface nunca entrega uma resposta que o eval não
        mediria.
        """
        x = self._etapa_guardrails({"pergunta": pergunta})
        if x["guardrail"] is not None:
            yield "final", self._etapa_resposta_fixa(x)
            return
        x["trechos"] = self._etapa_busca(x)
        if not x["trechos"]["usados"]:
            yield "final", self._etapa_sem_contexto(x)
            return

        usados = x["trechos"]["usados"]
        entrada = {"pergunta": pergunta, "contexto": prompt_rag.formatar_contexto(usados)}
        uso = UsageMetadataCallbackHandler()
        parcial = ""
        for pedaco in self.chain_stream.stream(entrada, config={"callbacks": [uso]}):
            parcial += pedaco
            yield "parcial", parcial
        texto = limpar_saida(parcial) if parcial.strip() else self.chain_resposta.invoke(entrada)
        r = self._pos_processar(texto, usados, x["trechos"]["descartados"], pergunta,
                                x["trechos"].get("injecao", []))
        entrada_tok = sum(u.get("input_tokens", 0) for u in uso.usage_metadata.values())
        saida_tok = sum(u.get("output_tokens", 0) for u in uso.usage_metadata.values())
        yield "final", r.model_copy(update={"tokens_servidor_entrada": entrada_tok,
                                            "tokens_servidor_saida": saida_tok})

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
    for f in r.descartados_por_injecao:
        print(f"  [injection {f['score']:.3f}] {f['documento']}, página {f['pagina']} ({f['motivo']})")
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
