"""
Capturas de tela da interface para o README e o relatório (gate da Fase 3).

    pip install playwright          # só para documentação; fora do requirements.txt
    python -m src.ferramentas.capturas_interface

Sobe `app/main.py` numa thread, abre no Microsoft Edge já instalado (canal
"msedge" do Playwright, sem baixar navegador), faz as três perguntas do gate
— uma respondível, uma de categoria nova (tarifa) e uma fora da base — e salva
`docs/img/interface_*.png`. Cada pergunta roda numa aba nova, que é também
uma sessão nova da interface.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

PERGUNTAS = {
    "interface_resposta": "Qual a potência do GW22K-HCA-20?",
    "interface_tarifa": "Quanto vou pagar por uma recarga de 30 kWh?",
    "interface_recusa": "Qual a previsão do tempo para amanhã em São Paulo?",
}
PORTA = 7861
PRONTO = """() => {
  const t = document.body.innerText;
  return !t.includes('Buscando trechos') && !t.includes('Gerando resposta')
         && (t.includes('Trechos enviados') || t.includes('Nenhum trecho') || t.includes('sem a resposta'));
}"""


def main():
    from playwright.sync_api import sync_playwright

    import main as app

    destino = RAIZ / "docs" / "img"
    destino.mkdir(parents=True, exist_ok=True)
    demo = app.montar_interface()
    demo.launch(server_port=PORTA, prevent_thread_lock=True, inbrowser=False, **app.opcoes_visuais())
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel="msedge", headless=True)
            for nome, pergunta in PERGUNTAS.items():
                pagina = navegador.new_page(viewport={"width": 1440, "height": 960})
                pagina.goto(f"http://127.0.0.1:{PORTA}/")
                caixa = pagina.locator("#entrada textarea")
                caixa.wait_for(timeout=60_000)
                caixa.fill(pergunta)
                caixa.press("Enter")
                pagina.wait_for_function(PRONTO, timeout=180_000)
                time.sleep(1.5)
                pagina.screenshot(path=str(destino / f"{nome}.png"), full_page=True)
                print(f"docs/img/{nome}.png")
                pagina.close()
            navegador.close()
    finally:
        demo.close()


if __name__ == "__main__":
    main()
