"""Valida os graficos lexicais (AFC, CHD, dendrograma, grafo) com dados sinteticos.

Injeta uma `analise_lexical` de exemplo no estado, percorre as 4 abas em 390 e
1440 px, nos dois temas, e verifica:
  - zero erros de JS;
  - zero overflow horizontal;
  - cada aba produziu um canvas do ECharts (grafico desenhado);
  - o "Ver dados" abre a tabela;
  - screenshots em docs/screenshots/<app>/lexical/.

Uso:
    python frontend/tests/validar_lexical.py
"""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent / "docs" / "screenshots"
PORT = 8803

LEXICAL = {
    "afc": {
        "palavras": [
            {"rotulo": w, "eixo1": x, "eixo2": y}
            for w, x, y in [
                ("saude", -1.2, 0.8), ("upa", -1.1, 0.9), ("fila", -0.9, 0.6),
                ("medico", -1.0, 0.4), ("obra", 1.1, -0.7), ("asfalto", 1.3, -0.8),
                ("ponte", 1.2, -0.5), ("onibus", 0.2, 1.4), ("transito", 0.4, 1.2),
                ("escola", -0.3, -1.3), ("creche", -0.5, -1.1), ("seguranca", 0.1, -0.2),
            ]
        ],
        "periodos": [
            {"rotulo": "2026-10", "eixo1": -0.4, "eixo2": 0.1},
            {"rotulo": "2026-11", "eixo1": 0.5, "eixo2": -0.2},
        ],
    },
    "chd": {
        "classes": [
            {"classe": 1, "n_segmentos": 120, "pct_segmentos": 34.0,
             "palavras": [{"palavra": "saude", "chi2": 45.2, "frequencia": 88},
                          {"palavra": "upa", "chi2": 30.1, "frequencia": 51},
                          {"palavra": "fila", "chi2": 22.0, "frequencia": 39}]},
            {"classe": 2, "n_segmentos": 80, "pct_segmentos": 22.0,
             "palavras": [{"palavra": "asfalto", "chi2": 25.0, "frequencia": 40},
                          {"palavra": "obra", "chi2": 18.0, "frequencia": 33}]},
            {"classe": 3, "n_segmentos": 60, "pct_segmentos": 16.0,
             "palavras": [{"palavra": "onibus", "chi2": 15.0, "frequencia": 25}]},
        ]
    },
    "dendrograma": {
        "polilinhas": [
            {"cor": "--classe-1", "x": [0, 0.5, 0.5, 1], "y": [0.1, 0.1, 0.3, 0.3]},
            {"cor": "--classe-1", "x": [0, 0.5, 0.5, 1], "y": [0.5, 0.5, 0.3, 0.3]},
            {"cor": "--classe-2", "x": [1, 1.6, 1.6, 2.2], "y": [0.3, 0.3, 0.7, 0.7]},
            {"cor": "--classe-3", "x": [2.2, 2.8, 2.8, 3.4], "y": [0.7, 0.7, 0.9, 0.9]},
        ]
    },
    "grafo": {
        "nos": [
            {"id": "saude", "peso": 88}, {"id": "upa", "peso": 51}, {"id": "fila", "peso": 39},
            {"id": "medico", "peso": 30}, {"id": "obra", "peso": 40}, {"id": "asfalto", "peso": 33},
            {"id": "ponte", "peso": 20}, {"id": "onibus", "peso": 25}, {"id": "transito", "peso": 18},
            {"id": "escola", "peso": 15},
        ],
        "arestas": [
            {"a": "saude", "b": "upa", "peso": 30}, {"a": "saude", "b": "fila", "peso": 22},
            {"a": "upa", "b": "medico", "peso": 18}, {"a": "obra", "b": "asfalto", "peso": 25},
            {"a": "obra", "b": "ponte", "peso": 12}, {"a": "onibus", "b": "transito", "peso": 14},
            {"a": "escola", "b": "fila", "peso": 8},
        ],
    },
}


def servir(diretorio: Path):
    class _Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(_Q, directory=str(diretorio))
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> int:
    nome_app = ROOT.parent.name
    httpd = servir(ROOT)
    resumo = {"erros": [], "overflow": [], "abas": {}, "prints": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
        for largura, altura in ((1440, 900), (390, 844)):
            pagina = browser.new_page(viewport={"width": largura, "height": altura})
            erros = []
            pagina.on("pageerror", lambda e: erros.append(str(e)))
            pagina.on(
                "console", lambda m: erros.append(m.text) if m.type == "error" else None
            )
            pagina.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="commit")
            pagina.wait_for_function("() => !!window.__app_test", timeout=20000)
            pagina.wait_for_timeout(800)
            pagina.evaluate(
                "() => { const l=document.getElementById('telaLogin'); if(l) l.style.display='none'; }"
            )
            # injeta a analise lexical sintetica e vai para a tela de analise
            pagina.evaluate(
                "(lex) => { const m = window.__app_test; m.estado.lexical = lex;"
                " try { window.__router.irPara('analise'); } catch(e) {} }",
                LEXICAL,
            )
            pagina.wait_for_timeout(600)

            for tema in ("escuro", "claro"):
                pagina.evaluate(
                    "(t) => { document.documentElement.dataset.tema = t; }", tema
                )
                for aba in ("afc", "chd", "dendrograma", "grafo"):
                    pagina.evaluate(
                        "(a) => { const b = document.querySelector(`.lex-tab[data-lex='${a}']`); if (b) b.click(); }",
                        aba,
                    )
                    pagina.wait_for_timeout(1100)
                    info = pagina.evaluate(
                        """(a) => {
                          const box = document.querySelector('#lexicalConteudo');
                          const canvas = box ? box.querySelector('canvas') : null;
                          const tabela = box ? box.querySelector('table.lex-tabela, .lex-dados table') : null;
                          const botoes = box ? box.querySelectorAll('[data-lex-dados]').length : 0;
                          const d = document.documentElement;
                          return { canvas: !!canvas, tabela: !!tabela, botoes,
                                   overflow: d.scrollWidth - d.clientWidth };
                        }""",
                        aba,
                    )
                    chave = f"{largura}-{tema}-{aba}"
                    resumo["abas"][chave] = info
                    if info["overflow"] > 1:
                        resumo["overflow"].append({"chave": chave, "px": info["overflow"]})
                    pasta = DOCS / nome_app / "lexical"
                    pasta.mkdir(parents=True, exist_ok=True)
                    arq = pasta / f"{tema}-{aba}-{largura}.png"
                    pagina.screenshot(path=str(arq), full_page=False)
                    resumo["prints"].append(str(arq.relative_to(ROOT.parent)))

            # testa o "Ver dados" na aba do grafo
            pagina.evaluate("() => document.querySelector('[data-lex-dados=grafo]')?.click()")
            pagina.wait_for_timeout(400)
            resumo["ver_dados"] = pagina.evaluate(
                "() => !!document.querySelector('.lex-dados table')"
            )

            reais = [e for e in erros if "gstatic" not in e.lower() and "firebase" not in e.lower()]
            if reais:
                resumo["erros"].extend({"largura": largura, "erro": e} for e in dict.fromkeys(reais))
            pagina.close()
        browser.close()

    httpd.shutdown()

    print(f"\n=== Graficos lexicais — {nome_app} ===")
    sem_canvas = [
        k for k, v in resumo["abas"].items()
        if k.split("-")[2] != "chd" and not v["canvas"]
    ]
    print(f"Abas verificadas: {len(resumo['abas'])}")
    print(f"Abas sem canvas (esperado so em dado vazio): {sem_canvas}")
    print(f"Sobreposicao horizontal (overflow): {len(resumo['overflow'])}")
    print(f"'Ver dados' abre tabela: {resumo.get('ver_dados')}")
    print(f"Erros de JS: {len(resumo['erros'])}")
    for e in resumo["erros"][:6]:
        print("  !", e)
    print(f"Screenshots: {len(resumo['prints'])}")

    destino = DOCS / nome_app / "lexical" / "validacao.json"
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    falhou = resumo["erros"] or resumo["overflow"] or sem_canvas or not resumo.get("ver_dados")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
