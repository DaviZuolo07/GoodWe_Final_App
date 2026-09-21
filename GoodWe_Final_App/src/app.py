"""
Chatbot ChargeOps no terminal (Sprint 03).

    python -m src.app                       # prompt v2, modelo principal, persona morador
    python -m src.app --persona sindico --prompt v1
    python -m src.app --perfil-demo         # carrega o perfil do caso da Sprint 2 (BYD Dolphin)

Comandos durante a conversa:
    /memoria   estado da janela de tokens, podas e fatos da sessão
    /extrair   próxima mensagem vai só para a chain estruturada (Pydantic) e mostra o JSON
    /limpar    nova sessão
    /sair
"""

from __future__ import annotations

import argparse
import json
import uuid

from dotenv import load_dotenv

load_dotenv()

PERFIL_DEMO = {"nome": "Morador Teste", "veiculo": "BYD Dolphin", "capacidade_bateria_kwh": 44.9,
               "potencia_carregador_kw": 7.4, "bloco": "A", "apartamento": "102"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="v2")
    ap.add_argument("--modelo", default=None)
    ap.add_argument("--persona", default="morador", choices=["morador", "sindico", "operador", "visitante"])
    ap.add_argument("--perfil-demo", action="store_true")
    ap.add_argument("--detalhes", action="store_true", help="mostra rota, tokens e cálculo a cada turno")
    ap.add_argument("--trace", action="store_true",
                    help="imprime cada passo da chain (prompt enviado, resposta crua do modelo)")
    a = ap.parse_args()

    from src.chain.builder import ChatbotChargeOps

    if a.trace:
        # Rastreio nativo do LangChain: mostra entrada e saída de cada Runnable.
        from langchain_core.globals import set_debug
        set_debug(True)

    bot = ChatbotChargeOps(versao_prompt=a.prompt, model=a.modelo)
    perfil = PERFIL_DEMO if a.perfil_demo else None
    sid = uuid.uuid4().hex
    modo_extrair = False
    print(f"ChargeOps (prompt {a.prompt}, persona {a.persona}). /memoria /extrair /limpar /sair\n")

    while True:
        try:
            msg = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        if msg == "/sair":
            break
        if msg == "/limpar":
            sid = uuid.uuid4().hex
            print("(nova sessão)\n")
            continue
        if msg == "/memoria":
            print(json.dumps(bot.memoria(sid), indent=2, ensure_ascii=False), "\n")
            continue
        if msg == "/extrair":
            modo_extrair = True
            print("(próxima mensagem: só extração estruturada)\n")
            continue
        if modo_extrair:
            modo_extrair = False
            try:
                print(bot.extrair(msg).model_dump_json(indent=2), "\n")
            except Exception as e:
                print(f"[validação recusou] {type(e).__name__}: {str(e)[:300]}\n")
            continue

        try:
            r = bot.responder(msg, session_id=sid, persona=a.persona, perfil=perfil)
        except Exception as erro:
            print(f"\n[falha ao falar com o modelo] {type(erro).__name__}: {str(erro)[:200]}")
            print("Rode 'python -m src.teste_auth' para descobrir a causa "
                  "(chave, host, nome do modelo ou Ollama local desligado).\n")
            continue
        print(f"chargeops> {r.texto}\n")
        if a.detalhes:
            servidor = r.tokens_servidor_entrada + r.tokens_servidor_saida
            prova = ("<- contados PELO MODELO: a chamada foi real" if servidor
                     else "<- ZERO: nenhuma chamada real chegou ao modelo")
            print(f"  [rota={r.rota} guardrail={r.categoria_guardrail} chamadas_llm={r.chamadas_llm} "
                  f"tokens_locais={r.tokens_prompt}+{r.tokens_resposta} estruturado={r.estruturado_valido}]")
            print(f"  [servidor: {r.tokens_servidor_entrada} entrada + {r.tokens_servidor_saida} saida "
                  f"= {servidor} tokens  {prova}]")
            if r.calculo:
                print(f"  [cálculo] {r.calculo}")
            print()


if __name__ == "__main__":
    main()
