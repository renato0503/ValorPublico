"""Validacao de UI: telas x temas x larguras, com dados simulados.

Serve ``frontend/`` local, esconde o gate de login (para fotografar o painel),
injeta dados pelo gancho ``window.__app_test``, percorre as rotas em 390 e
1440 px nos dois temas e:

  * salva screenshots em ``docs/screenshots/<app>/<tema>/<rota>-<w>.png``
  * detecta overflow horizontal (scrollWidth > clientWidth + 1)
  * coleta erros de JS (pageerror + console.error), ignorando ruido conhecido
    de rede/Firebase/gstatic do harness sem login
  * confere a legenda do donut (Chart.js) com fontColor definido

Uso:
    python frontend/tests/validar_ui.py
    python frontend/tests/validar_ui.py --app maximo
"""
from __future__ import annotations

import argparse
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
PORT = 8794

MOCK = {
    "total_clippings": 1200,
    "total_veiculos": 48,
    "audiencia_total": 900000,
    "valoracao_total": 125000.0,
    "valor_avpe_total": 90000.0,
    "distribuicao_categorias": {"Portal": 60, "TV": 20, "Rádio": 11},
    "distribuicao_sentimento": {"positivo": 60, "neutro": 50, "negativo": 20},
    "distribuicao_temas": {"Segurança": 30, "Saúde": 18},
    "distribuicao_mencoes": {"direta": 480, "indireta": 600, "indeterminada": 120},
    "distribuicao_papeis": {"protagonista": 200, "citada": 700},
    "porta_vozes": {"Ana Souza": 12, "Bruno Lima": 7},
    "compliance": {"artigos": {"Art. 40": 3}, "niveis": {"alerta": 3}, "total": 3},
    "radar": {"total": 29, "por_orgao": {"prefeitura": 12}, "com_simbolos_publicos": 2},
    "alertas": {
        "niveis": {"critico": 2, "alto": 5, "atencao": 3, "info": 1},
        "total": 11,
        "por_tipo": {"NEGATIVA_DIRETA": 2},
    },
    "cobertura": {
        "total": 1200,
        "pct_cobertura": 96.5,
        "sla_min_medio": 42.5,
        "sla_min_p95": 180.0,
        "com_veiculo": 1158,
        "sem_data_publicacao": 42,
    },
    "insights": {
        "maior_cobertura": {"categoria": "Portal", "mencoes": 600},
        "veiculo_destaque": "G1",
        "tendencia_positiva": 3.2,
    },
    "por_periodo": {
        "hoje": {"total_clippings": 12},
        "7d": {"total_clippings": 90},
        "30d": {},
        "todas": {},
    },
    "share_of_voice": [
        {"posicao": 1, "nome": "Eduardo Magalhaes", "clippings": 495, "pct_share": 6.86,
         "pct_positivo": 16.4, "pct_negativo": 9.7, "valor_estimado": 12000},
        {"posicao": 2, "nome": "Paula Calil", "clippings": 322, "pct_share": 4.46,
         "pct_positivo": 16.1, "pct_negativo": 7.8, "valor_estimado": 9000},
    ],
    "top_veiculos": [
        {"veiculo": "G1 MT", "clippings": 120, "tier": "Tier 1", "pct": 10.0},
        {"veiculo": "Folha do Estado", "clippings": 88, "tier": "Tier 2", "pct": 7.3},
    ],
    "noticias_recentes": [
        {"titulo": "Deputado apresenta projeto na ALMT", "veiculo": "G1 MT",
         "data": "2026-11-22T10:00:00Z", "url": "#", "sentimento": "positivo",
         "plataforma": "Web", "trecho": "Trecho de exemplo da materia."}
    ],
    "dias": {},
    "serie_sentimento": {},
    "nuvem_geral": {"mandato": 10, "saude": 7, "obra": 5},
    "nuvem_por_mes": {},
    "atualizado_em": "2026-11-23T10:00:00Z",
    "redes_sociais": {
        "por_rede": {"Instagram": 22, "Facebook": 14, "Twitter": 9, "TikTok": 3},
        "sentimento_por_rede": {"Instagram": {"positivo": 12, "neutro": 8, "negativo": 2}},
        "comentarios_total": 18,
        "recentes": [
            {"rede": "Instagram", "tipo": "Postagem", "agente": "Dep. Exemplo",
             "titulo": "Deputado publica sobre a sessao", "snippet": "Publicacao oficial sobre a votacao de hoje.",
             "url": "#", "data": "2026-11-22T10:00:00Z", "sentimento": "positivo", "confianca": "alta"},
            {"rede": "Facebook", "tipo": "Comentario", "agente": "Dep. Exemplo",
             "titulo": "Seguidor comentou", "snippet": "Parabens pelo trabalho!",
             "url": "#", "data": "2026-11-22T11:00:00Z", "sentimento": "positivo", "confianca": "baixa"},
        ],
    },
}

AGENTES_MOCK = [
    {"id": "samantha-iris", "nome_urna": "Samantha Iris", "cidade": "Cuiaba", "casa": "Camara Cuiaba", "esfera": "municipal", "partido": "PL", "cargo": "Vereadora"},
    {"id": "paula-calil", "nome_urna": "Paula Calil", "cidade": "Cuiaba", "casa": "Camara Cuiaba", "esfera": "municipal", "partido": "PL", "cargo": "Vereadora"},
    {"id": "adilsinho", "nome_urna": "Adilsinho", "cidade": "Varzea Grande", "casa": "Camara VG", "esfera": "municipal", "partido": "Republicanos", "cargo": "Vereador"},
    {"id": "janaina-riva", "nome_urna": "Janaina Riva", "cidade": "Mato Grosso", "casa": "ALMT", "esfera": "estadual", "partido": "MDB", "cargo": "Deputada Estadual"},
    {"id": "eduardo-botelho", "nome_urna": "Eduardo Botelho", "cidade": "Mato Grosso", "casa": "ALMT", "esfera": "estadual", "partido": "MDB", "cargo": "Deputado Estadual"},
    {"id": "ludio-cabral", "nome_urna": "Lúdio Cabral", "cidade": "Mato Grosso", "casa": "ALMT", "esfera": "estadual", "partido": "PT", "cargo": "Deputado Estadual"},
]

RUIDO = (
    "firebase",
    "gstatic",
    "failed to fetch",
    "network",
    "permission",
    "insufficient",
    "installations",
    "auth/",
    "offline",
    "net::err",
)


def servir(diretorio: Path):
    class _Quieto(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(_Quieto, directory=str(diretorio))

    class Servidor(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = Servidor(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=ROOT.parent.name)
    args = ap.parse_args()

    httpd = servir(ROOT)
    destino_base = DOCS / args.app
    resumo = {"prints": [], "overflow": [], "erros_js": [], "legendas_sem_cor": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
        for largura, altura in ((1440, 900), (390, 844)):
            pagina = browser.new_page(viewport={"width": largura, "height": altura})
            erros = []
            pagina.on("pageerror", lambda e: erros.append(str(e)))
            pagina.on(
                "console",
                lambda m: erros.append(m.text) if m.type == "error" else None,
            )
            pagina.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="commit")
            try:
                pagina.wait_for_function("() => !!window.__app_test", timeout=20000)
            except Exception:
                pass
            pagina.wait_for_timeout(1500)
            # esconde o gate de login para fotografar o painel
            pagina.evaluate(
                "() => { const l=document.getElementById('telaLogin'); if(l) l.style.display='none'; }"
            )
            pagina.evaluate(
                "(m) => { const mod=window.__app_test; mod.estado.ultimosDados=m;"
                " if(mod.renderizar) try{mod.renderizar(m)}catch(e){} }",
                MOCK,
            )
            pagina.wait_for_timeout(500)
            rotas = pagina.evaluate(
                "() => Array.from(document.querySelectorAll('.tela[data-tela]')).map(t=>t.dataset.tela)"
            ) or ["hoje"]

            for tema in ("claro", "escuro"):
                pagina.evaluate(
                    "(t) => { document.documentElement.dataset.tema=t; localStorage.setItem('vp_tema',t); }",
                    tema,
                )
                for rota in rotas:
                    pagina.evaluate("(r) => window.__router && window.__router.irPara(r)", rota)
                    pagina.wait_for_timeout(120)
                    # re-renderiza com a tela visivel (charts dimensionam certo)
                    pagina.evaluate(
                        "([m, ag]) => { const mod=window.__app_test; mod.estado.agentes=ag;"
                        " mod.estado.ultimosDados=m;"
                        " if(mod.renderizar) try{mod.renderizar(m)}catch(e){}"
                        " if(mod.renderizarCamadaDsm) try{mod.renderizarCamadaDsm()}catch(e){}"
                        " if(mod.renderizarParlamentaresPorCasa) try{mod.renderizarParlamentaresPorCasa()}catch(e){} }",
                        [MOCK, AGENTES_MOCK],
                    )
                    pagina.wait_for_timeout(400)
                    # overflow horizontal
                    overflow = pagina.evaluate(
                        "() => { const d=document.documentElement; return d.scrollWidth - d.clientWidth; }"
                    )
                    if overflow > 1:
                        resumo["overflow"].append(
                            {"largura": largura, "tema": tema, "rota": rota, "px": overflow}
                        )
                    # legenda do donut
                    sem_cor = pagina.evaluate(
                        "() => { const out=[]; if(!window.Chart) return out;"
                        " for(const id in (Chart.instances||{})){const ch=Chart.instances[id];"
                        " if(ch && ch.legend && ch.legend.legendItems)"
                        " for(const it of ch.legend.legendItems){ if(!it.fontColor) out.push((ch.canvas&&ch.canvas.id)||'?'); } }"
                        " return out; }"
                    )
                    if sem_cor:
                        resumo["legendas_sem_cor"].extend(sem_cor)
                    pasta = destino_base / tema
                    pasta.mkdir(parents=True, exist_ok=True)
                    arq = pasta / f"{rota}-{largura}.png"
                    pagina.screenshot(path=str(arq), full_page=True)
                    resumo["prints"].append(str(arq.relative_to(ROOT.parent)))

            reais = [e for e in erros if not any(r in e.lower() for r in RUIDO)]
            if reais:
                resumo["erros_js"].extend(
                    {"largura": largura, "erro": e} for e in dict.fromkeys(reais)
                )
            pagina.close()
        browser.close()

    httpd.shutdown()

    print(f"\n=== Validacao de UI — {args.app} ===")
    print(f"Screenshots: {len(resumo['prints'])}")
    print(f"Overflow horizontal: {len(resumo['overflow'])}")
    for o in resumo["overflow"]:
        print("  !", o)
    print(f"Legendas sem fontColor: {len(resumo['legendas_sem_cor'])}")
    print(f"Erros de JS (fora do ruido de rede): {len(resumo['erros_js'])}")
    for e in resumo["erros_js"][:10]:
        print("  !", e)

    json_saida = destino_base / "validacao.json"
    json_saida.parent.mkdir(parents=True, exist_ok=True)
    json_saida.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON: {json_saida.relative_to(ROOT.parent)}")

    falhou = resumo["overflow"] or resumo["erros_js"] or resumo["legendas_sem_cor"]
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()


