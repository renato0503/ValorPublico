"""Smoke test dos filtros, ícones e seletor de órgão (Playwright).

Uso:
    python frontend/tests/validar_filtros.py

Não precisa de login/Firebase: injeta um agregado de teste no gancho
`window.__app_test` e verifica o comportamento do front.
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8802

MOCK = {
    "total_clippings": 1200,
    "total_veiculos": 48,
    "audiencia_total": 900000,
    "valoracao_total": 125000.0,
    "distribuicao_sentimento": {"positivo": 60, "neutro": 50, "negativo": 20},
    "distribuicao_categorias": {"Portal": 60},
    "distribuicao_temas": {"Saúde": 30},
    "porta_vozes": {},
    "share_of_voice": [],
    "top_veiculos": [],
    "dias": {},
    "noticias_recentes": [
        {
            "titulo": f"Notícia de teste {i}",
            "texto_limpo": "Conteúdo de teste sobre saúde e segurança.",
            "veiculo": "Veículo A" if i % 2 == 0 else "Veículo B",
            "tipo_mencao": "direta" if i % 3 == 0 else "indireta",
            "sentimento": "positivo" if i % 2 == 0 else "neutro",
            "data_publicacao": "2026-11-24",
            "url": f"https://example.com/{i}",
        }
        for i in range(60)
    ],
    "por_periodo": {
        "hoje": {"total_clippings": 12},
        "7d": {"total_clippings": 90},
        "15d": {"total_clippings": 200},
        "30d": {"total_clippings": 500},
    },
}


def servir():
    class Quieto(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quieto, directory=str(ROOT))

    class Servidor(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = Servidor(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> None:
    httpd = servir()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, channel="chrome", args=["--no-sandbox"]
            )
            pagina = browser.new_page(viewport={"width": 1440, "height": 900})
            erros: list[str] = []
            pagina.on("pageerror", lambda e: erros.append(str(e)))
            pagina.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="commit")
            pagina.wait_for_function("() => !!window.__app_test", timeout=30000)
            pagina.evaluate(
                "() => { const l=document.getElementById('telaLogin'); if(l) l.style.display='none'; }"
            )
            pagina.evaluate(
                "(m) => { window.__app_test.estado.ultimosDados=m; window.__app_test.renderizar(m); }",
                MOCK,
            )
            pagina.wait_for_timeout(200)
            assert pagina.locator("#appSidebar").is_visible()
            assert not pagina.locator("#navPrincipal").is_visible()
            assert pagina.locator("#appSidebar a[data-rota]").count() >= 10
            pagina.wait_for_timeout(300)

            assert pagina.locator("#kpiClippings").inner_text().strip() == "1.200"

            pagina.click("#btnFiltros")
            pagina.wait_for_timeout(300)
            assert pagina.evaluate(
                "() => document.body.classList.contains('filtros-aberto')"
            )
            assert pagina.evaluate(
                "() => Math.abs(document.getElementById('filtrosLateral').getBoundingClientRect().right - window.innerWidth) < 1"
            )
            pagina.select_option("#filtroPeriodo", "7d")
            pagina.wait_for_timeout(300)
            assert pagina.locator("#kpiClippings").inner_text().strip() == "90"
            assert "periodo=7d" in pagina.evaluate("() => location.hash")
            pagina.click("#btnFecharFiltros")
            pagina.wait_for_timeout(100)
            assert not pagina.evaluate(
                "() => document.body.classList.contains('filtros-aberto')"
            )

            pagina.evaluate("() => window.__app_test.irPara('governo')")
            pagina.wait_for_timeout(200)
            assert not pagina.locator("#filtroParlamentarCampo").is_visible()
            pagina.evaluate("() => window.__app_test.irPara('simulacao')")
            pagina.wait_for_timeout(200)
            assert not pagina.locator("#btnFiltros").is_visible()
            pagina.evaluate("() => window.__app_test.irPara('edicao')")
            pagina.wait_for_timeout(200)
            assert pagina.locator("#btnFiltros").is_visible()

            # Clipping: busca e paginação.
            pagina.evaluate("() => window.__app_test.irPara('clipping')")
            pagina.evaluate("(m) => window.__app_test.telas.definirDados(m)", MOCK)
            pagina.wait_for_timeout(250)
            assert pagina.locator("#corpoClipping tr").count() == 25
            pagina.fill("#filtroClipBusca", "Notícia de teste 1")
            pagina.wait_for_timeout(250)
            assert pagina.locator("#corpoClipping tr").count() > 0
            pagina.fill("#filtroClipBusca", "")
            pagina.wait_for_timeout(250)
            pagina.click("#paginacaoClipping button[data-pagina='2']")
            pagina.wait_for_timeout(250)
            assert pagina.locator("#corpoClipping tr").count() == 25

            # Seletor de órgão: modal central, 2 colunas e sem rolagem no desktop.
            pagina.evaluate(
                """() => {
                  const t=document.getElementById('telaOrgao');
                  t.classList.add('ativo'); t.setAttribute('aria-hidden','false');
                  const g=document.getElementById('orgaoCards');
                  g.innerHTML=['cuiaba','varzea-grande','almt','governo-mt'].map(
                    (s,i)=>`<a href="#" class="orgao-card"><span class="orgao-sigla">${s}</span><span class="orgao-rotulo">Instituição ${i+1}</span><span class="orgao-cidade">Cidade</span></a>`
                  ).join('');
                }"""
            )
            pagina.wait_for_timeout(150)
            medidas = pagina.evaluate(
                """() => {
                  const f=document.querySelector('#telaOrgao .login-folha');
                  const r=f.getBoundingClientRect();
                  return {
                    scrollH:f.scrollHeight, clientH:f.clientHeight,
                    top:r.top, bottom:r.bottom, vh:innerHeight,
                    colunas:getComputedStyle(document.getElementById('orgaoCards')).gridTemplateColumns.split(' ').length,
                  };
                }"""
            )
            assert medidas["scrollH"] <= medidas["clientH"] + 1, medidas
            assert 0 <= medidas["top"] and medidas["bottom"] <= medidas["vh"] + 1, medidas
            assert medidas["colunas"] == 2, medidas
            assert pagina.locator("button .icone-btn").count() >= 30

            # Semana e exportação CSV do Governo.
            pagina.evaluate("() => { const t=document.getElementById('telaOrgao'); t.classList.remove('ativo'); t.setAttribute('aria-hidden','true'); }")
            pagina.evaluate("() => window.__app_test.irPara('governo')")
            pagina.evaluate(
                """() => window.__app_test.governo.definirDados({
                  casa: { total_clippings: 10, valoracao_total: 100, por_periodo: { "7d": { total_clippings: 10, valoracao_total: 100, distribuicao_sentimento: { positivo: 6, neutro: 3, negativo: 1 }, noticias_recentes: [{ titulo: "Teste", veiculo: "V", data_publicacao: "2026-11-24", sentimento: "positivo" }] } },
                          distribuicao_sentimento: { positivo: 6, neutro: 3, negativo: 1 },
                          noticias_recentes: [{ titulo: 'Teste', veiculo: 'V', data_publicacao: '2026-11-24', sentimento: 'positivo' }] },
                  secretarias: [], governador: null, interino: null
                })"""
            )
            pagina.wait_for_timeout(200)
            assert pagina.locator("#filtroSemanaGovernador option").count() == 12
            with pagina.expect_download() as download:
                pagina.click("#btnExportarGoverno")
            assert download.value.suggested_filename.endswith(".csv")

            # Zero enganoso: sem tendências, o KPI deve ser "—" e "sem base".
            pagina.evaluate("() => window.__app_test.irPara('tendencias')")
            pagina.wait_for_timeout(300)
            assert pagina.locator("#kpiTendInteresse .kpi-valor").inner_text().strip() == "—"
            assert "kpi-sem-base" in pagina.locator("#kpiTendInteresse").get_attribute("class")

            # Período sem recorte: não pode cair no total geral.
            pagina.evaluate(
                "() => { const m=window.__app_test.estado.ultimosDados; m.por_periodo['30d']={}; window.__app_test.renderizar(m); }"
            )
            pagina.evaluate("() => window.__app_test.irPara('edicao')")
            pagina.wait_for_timeout(200)
            pagina.click("#btnFiltros")
            pagina.select_option("#filtroPeriodo", "30d")
            pagina.wait_for_timeout(300)
            assert pagina.locator("#kpiClippings").inner_text().strip() == "—", pagina.locator("#kpiClippings").inner_text()

            # Mobile: menu em hambúrguer com conta/órgão e fecha por Esc.
            pagina.evaluate(
                "() => { document.body.classList.remove('filtros-aberto'); const b=document.getElementById('filtrosBackdrop'); if(b) b.hidden=true; }"
            )
            pagina.set_viewport_size({"width": 390, "height": 844})
            pagina.wait_for_timeout(200)
            assert pagina.locator("#btnMenu").is_visible()
            assert not pagina.locator("#navPrincipal").is_visible()
            pagina.click("#btnMenu")
            pagina.wait_for_timeout(150)
            assert pagina.locator("#navPrincipal").is_visible()
            assert pagina.locator("#navAuthMobile").is_visible()
            assert pagina.locator("#navOrgaoMobile").is_visible()
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(150)
            assert not pagina.locator("#navPrincipal").is_visible()
            assert not erros, erros[:5]
            print("OK — filtros, período, clipping, seletor de órgão e ícones.")
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()









