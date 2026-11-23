"""Auditoria automatica de contraste (WCAG 2.1) do painel, nos dois temas.

Serve a pasta ``frontend/`` localmente, injeta dados simulados pelo gancho
``window.__app_test`` (nao precisa de Firestore nem de login), percorre todas
as rotas/telas em cada tema e mede a razao de contraste de cada no de texto
visivel contra o fundo efetivo (sobe na arvore ate o primeiro
``background-color`` opaco).

Uso:
    python frontend/tests/contraste.py
    python frontend/tests/contraste.py --json ..\\..\\docs\\contraste.json
    python frontend/tests/contraste.py --max-itens 400

Criterio: WCAG AA -- >= 4.5:1 para texto normal e >= 3:1 para texto grande
(>= 18px, ou >= 14px em negrito). Sai com codigo 1 se houver violacao.

O mesmo arquivo roda nos dois apps (a lista de rotas e lida do DOM, entao
``.tela[data-tela]`` do Assessor e do Valor sao descobertas sozinhas).
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
PORT = 8791

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
        "hoje": {
            "total_clippings": 12,
            "distribuicao_sentimento": {"positivo": 6, "neutro": 4, "negativo": 2},
        },
        "7d": {
            "total_clippings": 90,
            "distribuicao_sentimento": {"positivo": 40, "neutro": 30, "negativo": 20},
        },
        "30d": {},
        "todas": {},
    },
    "share_of_voice": [
        {
            "posicao": 1,
            "nome": "Eduardo Magalhaes",
            "clippings": 495,
            "pct_share": 6.86,
            "pct_positivo": 16.4,
            "pct_negativo": 9.7,
            "valor_estimado": 12000,
        },
        {
            "posicao": 2,
            "nome": "Paula Calil",
            "clippings": 322,
            "pct_share": 4.46,
            "pct_positivo": 16.1,
            "pct_negativo": 7.8,
            "valor_estimado": 9000,
        },
        {
            "posicao": 3,
            "nome": "Ilde Taques",
            "clippings": 294,
            "pct_share": 4.07,
            "pct_positivo": 24.1,
            "pct_negativo": 7.5,
            "valor_estimado": 8000,
        },
    ],
    "top_veiculos": [
        {"veiculo": "G1 MT", "clippings": 120, "tier": "Tier 1", "pct": 10.0},
        {"veiculo": "Folha do Estado", "clippings": 88, "tier": "Tier 2", "pct": 7.3},
    ],
    "noticias_recentes": [
        {
            "titulo": "Deputado apresenta projeto na ALMT",
            "veiculo": "G1 MT",
            "data": "2026-11-22T10:00:00Z",
            "url": "#",
            "sentimento": "positivo",
            "plataforma": "Web",
            "trecho": "Trecho de exemplo da materia para medir contraste.",
        }
    ],
    "dias": {},
    "serie_sentimento": {},
    "nuvem_geral": {"mandato": 10, "saude": 7, "obra": 5},
    "nuvem_por_mes": {},
    "atualizado_em": "2026-11-23T10:00:00Z",
    "redes_sociais": {
        "por_rede": {"Instagram": 22, "Facebook": 14, "Twitter": 9},
        "sentimento_por_rede": {"Instagram": {"positivo": 12, "neutro": 8, "negativo": 2}},
        "comentarios_total": 18,
        "recentes": [
            {
                "rede": "Instagram",
                "tipo": "Postagem",
                "agente": "Deputado Exemplo",
                "titulo": "Deputado publica sobre sessao",
                "snippet": "Publicacao oficial sobre a votacao de hoje.",
                "url": "#",
                "data": "2026-11-22T10:00:00Z",
                "sentimento": "positivo",
                "confianca": "alta",
            },
            {
                "rede": "Facebook",
                "tipo": "Comentario",
                "agente": "Deputado Exemplo",
                "titulo": "Seguidor comentou",
                "snippet": "Parabens pelo trabalho!",
                "url": "#",
                "data": "2026-11-22T11:00:00Z",
                "sentimento": "positivo",
                "confianca": "baixa",
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# JS de medicao: percorre os nos de texto visiveis e calcula contraste.
# ---------------------------------------------------------------------------
JS_MEDIR = r"""
() => {
  function toRGB(c) {
    if (!c) return null;
    c = String(c).trim();
    let m = c.match(/^rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    m = c.match(/^#([0-9a-fA-F]{3,8})$/);
    if (m) {
      let h = m[1];
      if (h.length === 3) h = h.split("").map((x) => x + x).join("");
      if (h.length === 4) h = h.split("").map((x) => x + x).join("");
      const n = parseInt(h.slice(0, 6), 16);
      const a = h.length >= 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1;
      return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a };
    }
    if (c === "transparent") return { r: 0, g: 0, b: 0, a: 0 };
    return null;
  }
  function lin(c) {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  }
  function lum(rgb) {
    return 0.2126 * lin(rgb.r) + 0.7152 * lin(rgb.g) + 0.0722 * lin(rgb.b);
  }
  function razao(fg, bg) {
    const l1 = lum(fg) + 0.05;
    const l2 = lum(bg) + 0.05;
    return l1 > l2 ? l1 / l2 : l2 / l1;
  }
  function over(fg, bg) {
    const a = fg.a == null ? 1 : fg.a;
    return {
      r: Math.round(fg.r * a + bg.r * (1 - a)),
      g: Math.round(fg.g * a + bg.g * (1 - a)),
      b: Math.round(fg.b * a + bg.b * (1 - a)),
      a: 1,
    };
  }
  function paradasGradiente(img) {
    const out = [];
    if (!img || img === "none") return out;
    const re = /(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})/g;
    let m;
    while ((m = re.exec(img))) {
      const c = toRGB(m[1]);
      if (c) out.push(c);
    }
    return out;
  }
  function fundosCandidatos(el) {
    const tema = document.documentElement.dataset.tema;
    const basePagina =
      tema === "claro"
        ? { r: 242, g: 246, b: 251, a: 1 }
        : { r: 7, g: 12, b: 22, a: 1 };
    let no = el;
    while (no && no.nodeType === 1) {
      const st = getComputedStyle(no);
      const bc = toRGB(st.backgroundColor);
      const img = st.backgroundImage || "";
      const stops =
        img && img !== "none" ? paradasGradiente(img).filter((s) => s.a > 0.02) : [];
      const bcOp = bc && bc.a > 0.9;
      if (img && img.includes("url(")) return null; // fundo é midia: revisao visual
      if (stops.length) {
        let under = bcOp ? bc : basePagina;
        const cands = stops.map((s) => over(s, under));
        if (bcOp) cands.push(bc);
        return cands;
      }
      if (bcOp) return [bc];
      no = no.parentElement;
    }
    return [basePagina];
  }
  function visivel(el) {
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || Number(st.opacity) === 0) {
      return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  }
  function seletor(el) {
    const partes = [];
    let no = el;
    for (let i = 0; i < 4 && no && no.nodeType === 1; i++) {
      let s = no.tagName.toLowerCase();
      if (no.id) {
        s += "#" + no.id;
        partes.unshift(s);
        break;
      }
      if (no.classList && no.classList.length) {
        s += "." + Array.from(no.classList).slice(0, 2).join(".");
      }
      partes.unshift(s);
      no = no.parentElement;
    }
    return partes.join(" > ");
  }

  const achados = [];
  const vistos = new Set();
  let conta = 0;
  const todos = document.querySelectorAll("body *");
  for (const el of todos) {
    if (!visivel(el)) continue;
    let proprio = "";
    for (const n of el.childNodes) {
      if (n.nodeType === 3) proprio += n.nodeValue;
    }
    proprio = proprio.replace(/\s+/g, " ").trim();
    if (!proprio) continue;
    const st = getComputedStyle(el);
    const fgBruto = toRGB(st.color);
    if (!fgBruto) continue;
    const tamanho = parseFloat(st.fontSize) || 16;
    const peso = Number(st.fontWeight) || 400;
    const grande = tamanho >= 18 || (tamanho >= 14 && peso >= 700);
    const minimo = grande ? 3 : 4.5;
    // pior caso entre os fundos candidatos (gradiente/transparência)
    const candidatos = fundosCandidatos(el);
    if (!candidatos) continue; // sobre midia (imagem de fundo)
    let pior = null;
    let piorBg = null;
    for (const bg of candidatos) {
      const fg = over(fgBruto, bg);
      const r = razao(fg, bg);
      if (pior === null || r < pior) {
        pior = r;
        piorBg = { fg, bg };
      }
    }
    conta++;
    const chave = seletor(el) + "|" + proprio.slice(0, 30);
    if (pior + 1e-6 < minimo && !vistos.has(chave)) {
      vistos.add(chave);
      achados.push({
        seletor: seletor(el),
        texto: proprio.slice(0, 60),
        cor: `rgb(${piorBg.fg.r}, ${piorBg.fg.g}, ${piorBg.fg.b})`,
        fundo: `rgb(${piorBg.bg.r}, ${piorBg.bg.g}, ${piorBg.bg.b})`,
        tamanho: Math.round(tamanho),
        peso,
        minimo,
        razao: Math.round(pior * 100) / 100,
      });
    }
  }
  // Legenda do donut (Chart.js) -- fontColor de cada item.
  const legendas = [];
  if (window.Chart) {
    for (const id in Chart.instances || {}) {
      const ch = Chart.instances[id];
      if (!ch || !ch.legend || !ch.legend.legendItems) continue;
      for (const it of ch.legend.legendItems) {
        legendas.push({
          canvas: ch.canvas && ch.canvas.id,
          texto: it.text,
          fontColor: it.fontColor || null,
        });
      }
    }
  }
  return { total_textos: conta, achados, legendas };
}
"""

JS_INJETAR = r"""
(m) => {
  const mod = window.__app_test;
  if (!mod) return "sem-hook";
  try {
    mod.estado.ultimosDados = m;
    if (typeof mod.renderizar === "function") mod.renderizar(m);
  } catch (e) {
    return "erro-render:" + (e && e.message ? e.message : e);
  }
  return "ok";
}
"""

JS_TEMA = r"""
(t) => {
  document.documentElement.dataset.tema = t;
  localStorage.setItem("vp_tema", t);
  const mod = window.__app_test;
  try {
    if (mod && mod.estado && mod.estado.ultimosDados && typeof mod.renderizar === "function") {
      mod.renderizar(mod.estado.ultimosDados);
    }
  } catch (e) {
    /* ignora */
  }
  if (window.Chart && window.Chart.defaults) {
    /* nada: o render usa corTema */
  }
  return document.documentElement.dataset.tema;
}
"""

JS_ROTAS = r"""
() => Array.from(document.querySelectorAll(".tela[data-tela]")).map(t => t.dataset.tela)
"""


def servir(diretorio: Path):
    class _Quieto(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(_Quieto, directory=str(diretorio))
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def auditar(app_nome: str, max_itens: int):
    httpd = servir(ROOT)
    temas = ["escuro", "claro"]
    violacoes = []
    resumo = {}
    legendas_todas = []
    erros_js = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
        pagina = browser.new_page(viewport={"width": 1440, "height": 1000})
        pagina.on("pageerror", lambda e: erros_js.append(str(e)))
        pagina.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="commit")
        try:
            pagina.wait_for_function("() => !!window.__app_test", timeout=20000)
        except Exception:
            pass
        pagina.wait_for_timeout(2000)
        pagina.evaluate(JS_INJETAR, MOCK)
        pagina.wait_for_timeout(600)
        rotas = pagina.evaluate(JS_ROTAS)
        if not rotas:
            rotas = ["hoje"]
        for tema in temas:
            pagina.evaluate(JS_TEMA, tema)
            pagina.wait_for_timeout(350)
            for rota in rotas:
                try:
                    pagina.evaluate("(r) => window.__router && window.__router.irPara(r)", rota)
                except Exception:
                    pass
                pagina.wait_for_timeout(250)
                dados = pagina.evaluate(JS_MEDIR)
                resumo[f"{tema}/{rota}"] = dados["total_textos"]
                legendas_todas.extend(dados.get("legendas", []))
                for a in dados["achados"]:
                    a["tema"] = tema
                    a["rota"] = rota
                    violacoes.append(a)
        browser.close()

    httpd.shutdown()

    violacoes.sort(key=lambda x: (x["tema"], x["rota"], x["razao"]))
    print(f"\n=== Contraste WCAG — {app_nome} ({ROOT}) ===")
    for chave, n in resumo.items():
        print(f"  {chave:28s} {n:4d} nos de texto")
    print(f"\nLegendas de grafico encontradas: {len(legendas_todas)}")
    sem_font = [l for l in legendas_todas if not l.get("fontColor")]
    if sem_font:
        print(f"  AVISO: {len(sem_font)} itens de legenda sem fontColor definido:")
        for l in sem_font[:6]:
            print(f"    - {l.get('canvas')}: {l.get('texto')}")
    if erros_js:
        print(f"\nErros de JS durante a auditoria: {len(erros_js)}")
        for e in erros_js[:5]:
            print("  !", e)
    print(f"\nViolacoes: {len(violacoes)}")
    for v in violacoes[:max_itens]:
        print(
            f"  [{v['tema']}/{v['rota']}] {v['razao']:.2f} < {v['minimo']} "
            f"({v['tamanho']}px/{v['peso']}) {v['cor']} sobre {v['fundo']} :: "
            f"{v['texto']!r}  ({v['seletor']})"
        )
    return violacoes, legendas_todas, erros_js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="", help="grava o resultado em JSON")
    ap.add_argument("--max-itens", type=int, default=200)
    ap.add_argument("--app", default=ROOT.parent.name)
    args = ap.parse_args()

    violacoes, legendas, erros = auditar(args.app, args.max_itens)

    if args.json:
        destino = Path(args.json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(
                {"app": args.app, "violacoes": violacoes, "legendas": legendas, "erros_js": erros},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nJSON gravado em {destino}")

    sys.exit(1 if violacoes else 0)


if __name__ == "__main__":
    main()
