"""Testa a renderizacao DUPLA das telas novas (regressao do erro
'Cannot set properties of undefined (setting innerHTML)').

Renderiza 3 vezes seguidas e garante:
  - zero erro de JS;
  - o conjunto de ids dos blocos de grafico nao muda entre renderizacoes
    (era exatamente o que quebrava: o cartao de grafico apagava o id e a
     proxima renderizacao caia em undefined.innerHTML);
  - todo bloco de grafico tem id nao vazio.

Funciona nos dois apps (nao depende dos nomes das telas).

Uso:
    python frontend/tests/teste_render_duplo.py
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

RUIDO = ("gstatic", "fonts.googleapis", "favicon", "manifest", "net::err",
         "failed to fetch", "permission", "insufficient", "auth/", "installations")

SCRIPT = """() => {
  const t = window.__app_test?.telas;
  if (!t) return { erro: 'sem modulo telas' };
  const lerIds = () =>
    Array.from(document.querySelectorAll('.grafico-area'))
      .map((el, i) => el.id || `(sem-id-${i})`)
      .sort();
  const rodadas = [];
  for (let i = 0; i < 3; i++) {
    try { t.renderizar(); } catch (e) { return { erro: String(e) }; }
    rodadas.push(lerIds());
  }
  return { rodadas };
}"""


def servir(diretorio: Path):
    class _Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(_Q, directory=str(diretorio))
    # Porta 0 = o sistema escolhe uma livre (evita TIME_WAIT de testes anteriores)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    porta = httpd.server_address[1]
    return httpd, porta


def main() -> int:
    httpd, porta = servir(ROOT)
    erros: list[str] = []
    detalhes = {}

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True, args=["--no-sandbox"])
        for largura, altura in ((1440, 900), (390, 844)):
            pagina = navegador.new_page(viewport={"width": largura, "height": altura})
            pagina.on("pageerror", lambda e: erros.append(str(e)))
            pagina.on(
                "console", lambda m: erros.append(m.text) if m.type == "error" else None
            )
            pagina.goto(f"http://127.0.0.1:{porta}/index.html", wait_until="commit")
            pagina.wait_for_function("() => !!window.__app_test", timeout=60000)
            pagina.wait_for_timeout(800)
            pagina.evaluate(
                "() => { const l=document.getElementById('telaLogin'); if(l) l.style.display='none'; }"
            )
            detalhes[largura] = pagina.evaluate(SCRIPT)
            pagina.close()
        navegador.close()
    httpd.shutdown()

    reais = [e for e in dict.fromkeys(erros) if not any(x in e.lower() for x in RUIDO)]
    print("erros de JS:", len(reais))
    for e in reais[:6]:
        print("  !", e)

    falhou = bool(reais)
    for largura, info in detalhes.items():
        if info.get("erro"):
            print(f"  ! {largura}px: {info['erro']}")
            falhou = True
            continue
        rodadas = info["rodadas"]
        print(f"  {largura}px: {len(rodadas[0])} blocos de grafico, ids estaveis =", rodadas[0] == rodadas[1] == rodadas[2])
        if not (rodadas[0] == rodadas[1] == rodadas[2]):
            print(f"    ! ids mudaram: {rodadas}")
            falhou = True
        if any(i.startswith("(sem-id") for i in rodadas[0]):
            print(f"    ! bloco sem id: {rodadas[0]}")
            falhou = True
        if not rodadas[0]:
            print("    ! nenhum bloco de grafico renderizado")
            falhou = True

    print("RESULTADO:", "FALHOU" if falhou else "OK")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())


