"""
Servidor Ollama FALSO para smoke test offline (sem cota, sem internet).

    python -m tests.servidor_ollama_falso            # escuta em 127.0.0.1:11999
    OLLAMA_HOST=http://127.0.0.1:11999 python -m evals.runner --adaptador lcel --sem-juiz

Implementa /api/chat (streaming NDJSON e não-streaming) e /api/tags. Serve
para provar que a FIAÇÃO funciona ponta a ponta (legado, LCEL, extração JSON,
memória, runner). As respostas são fixas: os números gerados com ele NÃO
são resultados de qualidade e nunca vão para o relatório.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORTA = 11999


def _extrair(texto: str) -> dict:
    """Extração ingênua por regex — só para devolver um JSON plausível."""
    def num(rx):
        m = re.search(rx, texto, re.I)
        return m.group(1).replace(",", ".") if m else None
    return {
        "intencao": "estimativa_tempo" if re.search(r"quanto tempo|demora|leva", texto, re.I) else "outro",
        "capacidade_bateria_kwh": num(r"(\d+(?:[.,]\d+)?)\s*kwh"),
        "soc_atual_pct": num(r"(?:com|em|está com)\s*(\d+)\s*%"),
        "soc_alvo_pct": num(r"at[ée]\s*(\d+)\s*%"),
        "potencia_carregador_kw": num(r"(\d+(?:[.,]\d+)?)\s*kw(?!h)"),
        "confianca": 0.8,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, status=200):
        corpo = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        self._json({"models": [{"name": "gpt-oss:120b"}, {"name": "gemma4:31b"}]})

    def do_POST(self):
        dados = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        msgs = dados.get("messages", [])
        ultima = msgs[-1]["content"] if msgs else ""
        if dados.get("format") == "json":
            m = re.search(r"<mensagem_atual>\s*(.*?)\s*</mensagem_atual>", ultima, re.S)
            conteudo = json.dumps(_extrair(m.group(1) if m else ultima))
        else:
            conteudo = ("Resposta de teste do servidor falso sobre recarga de veículos elétricos. "
                        "Este texto não tem valor de avaliação.")
        n_in = sum(len(str(x.get("content", ""))) // 4 for x in msgs)
        final = {"model": dados.get("model"), "created_at": "2026-09-19T00:00:00Z",
                 "done": True, "done_reason": "stop", "prompt_eval_count": n_in,
                 "eval_count": len(conteudo) // 4, "total_duration": 1, "load_duration": 1,
                 "prompt_eval_duration": 1, "eval_duration": 1}
        if dados.get("stream", True):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            parte = {"model": dados.get("model"), "created_at": "2026-09-19T00:00:00Z",
                     "message": {"role": "assistant", "content": conteudo}, "done": False}
            self.wfile.write((json.dumps(parte) + "\n").encode())
            self.wfile.write((json.dumps({**final, "message": {"role": "assistant", "content": ""}}) + "\n").encode())
        else:
            self._json({**final, "message": {"role": "assistant", "content": conteudo}})


def iniciar(porta: int = PORTA) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    print(f"Servidor Ollama falso em http://127.0.0.1:{PORTA}  (Ctrl+C para sair)")
    ThreadingHTTPServer(("127.0.0.1", PORTA), Handler).serve_forever()
