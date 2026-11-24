"""Relatorio do clipping do Governo de Mato Grosso (XLSX + PDF + CSV).

Le o JSONL gerado por `coletar_governo_mt.py` e monta:
  * **Resumo** — total, periodo, escopo, valor/sentimento, cobertura por pasta;
  * **Por secretaria** — uma aba por pasta, com as manchetes e os links;
  * **Governador** e **Interino** — o que foi publicado sobre cada um;
  * **Lista completa** — data, titulo, veiculo, pasta, escopo, link;
  * **Contexto de MT** — as noticias de outras instituicoes (para transparencia).

O PDF usa o mesmo HTML do app (Playwright) e abre com "Como ler este relatorio"
(plano 17 §4.4).

Uso (a partir de `backend/`):
    python scripts/relatorio_governo_mt.py
    python scripts/relatorio_governo_mt.py --jsonl data/governo_mt/noticias-2026-11-24.jsonl
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from config.settings import BASE_DIR

logger = get_logger(__name__)

SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"
PASTA_PADRAO = BASE_DIR / "data" / "governo_mt"

CSS = """
  @page { size: A4; margin: 16mm; }
  * { box-sizing: border-box; }
  body { font-family: Inter, Arial, sans-serif; color: #0f172a; font-size: 10pt; line-height: 1.5; }
  h1 { font-size: 19pt; margin: 0 0 2mm; }
  h2 { font-size: 13pt; margin: 8mm 0 2mm; padding-bottom: 1mm; border-bottom: 1px solid #cbd5e1; }
  h3 { font-size: 11pt; margin: 5mm 0 1mm; }
  .capa { padding: 8mm 0 5mm; border-bottom: 3px double #1e3a5f; }
  .capa .eyebrow { text-transform: uppercase; letter-spacing: .1em; font-size: 8.5pt; color: #475569; }
  .numeros { display: flex; gap: 7mm; margin-top: 5mm; }
  .numeros .n { flex: 1; border: 1px solid #cbd5e1; border-radius: 2mm; padding: 2mm 3mm; }
  .numeros .n b { display: block; font-size: 15pt; }
  .numeros .n span { font-size: 8pt; color: #475569; }
  table { width: 100%; border-collapse: collapse; margin-top: 2mm; font-size: 8.6pt; }
  th, td { text-align: left; padding: 1.6mm 2mm; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
  th { background: #f1f5f9; font-size: 8.2pt; text-transform: uppercase; letter-spacing: .03em; color: #334155; }
  .noticia { margin: 0 0 2.4mm; padding-left: 3mm; border-left: 2px solid #cbd5e1; page-break-inside: avoid; }
  .noticia b { font-size: 9.6pt; }
  .noticia .meta { font-size: 8pt; color: #475569; }
  .noticia a { color: #1d4ed8; word-break: break-all; font-size: 7.6pt; }
  .como-ler { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 2mm; padding: 3mm 4mm; }
  .como-ler ol { margin: 2mm 0 0 5mm; padding: 0; }
  .como-ler li { margin-bottom: 1.2mm; }
  .selo { display: inline-block; padding: .6mm 2mm; border-radius: 1mm; font-size: 8pt;
          background: #fef3c7; border: 1px solid #a16207; color: #854d0e; }
  .rodape { margin-top: 8mm; padding-top: 2mm; border-top: 1px solid #cbd5e1; font-size: 7.6pt; color: #64748b; }
"""


def carregar_itens(caminho: Path) -> list[dict]:
    itens = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        item = json.loads(linha)
        # a data pode ter sido gravada como texto (default=str no jsonl)
        bruto = item.get("data")
        if isinstance(bruto, str):
            try:
                item["data"] = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
            except ValueError:
                item["data"] = None
        itens.append(item)
    return itens


def _data(item: dict) -> str:
    bruto = str(item.get("data") or "")
    return bruto[:10]


def _titulo(item: dict) -> str:
    return item.get("titulo") or "(sem título)"


def _html_linha(item: dict) -> str:
    pasta = ", ".join(item.get("siglas") or []) or "geral"
    return (
        f'<div class="noticia"><b>{html.escape(_titulo(item))}</b>'
        f'<div class="meta">{html.escape(_data(item))} · {html.escape(item.get("veiculo") or "—")}'
        f' · {html.escape(pasta)}</div>'
        f'<a href="{html.escape(item.get("url") or "")}">{html.escape(item.get("url") or "")}</a></div>'
    )


def construir_html(itens: list[dict], seed: dict, resumo: dict) -> str:
    nome_org = seed.get("orgao", {}).get("nome", "Governo do Estado de Mato Grosso")
    governador = seed.get("governador", {}).get("nome", "")
    interino = seed.get("interino", {}).get("nome", "")
    por_pasta: dict[str, list[dict]] = defaultdict(list)
    for item in itens:
        if item.get("escopo") != "governo-estado":
            continue
        for sigla in item.get("siglas") or []:
            if sigla:
                por_pasta[sigla].append(item)
    do_governador = [i for i in itens if "governador" in (i.get("alvos") or [])]
    do_interino = [i for i in itens if "interino" in (i.get("alvos") or [])]
    contexto = [i for i in itens if i.get("escopo") in ("instituicoes-mt", "geral-mt")]

    partes = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>Clipping do Governo de MT — {nome_org}</title><style>{CSS}</style></head><body>",
        # capa
        "<section class='capa'>",
        "<p class='eyebrow'>Clipping institucional · relatório para a Secom</p>",
        f"<h1>Governo do Estado de Mato Grosso</h1>",
        "<p>Como a imprensa e o público falaram do governo no período</p>",
        "<div class='numeros'>",
        f"<div class='n'><b>{resumo['total']}</b><span>notícias coletadas</span></div>",
        f"<div class='n'><b>{resumo['do_governo_do_estado']}</b><span>sobre o Governo do Estado</span></div>",
        f"<div class='n'><b>{len(por_pasta)}</b><span>pastas com cobertura</span></div>",
        f"<div class='n'><b>{len(do_governador)}</b><span>citando o governador</span></div>",
        f"<div class='n'><b>{len(do_interino)}</b><span>citando o interino</span></div>",
        "</div>",
        f"<p style='margin-top:3mm;font-size:8.6pt;color:#475569'>Período: {str(resumo['periodo']['de'])[:10]} até {str(resumo['periodo']['ate'])[:10]} · "
        "Fonte oficial do governo: portal.mt.gov.br · agregador: Google News · "
        "classificação por pasta: dicionário oficial de secretarias (comprovado por fonte oficial)</p>",
        "</section>",
        # como ler
        "<section class='como-ler'><h2>Como ler este relatório</h2><ol>",
        "<li><b>Notícias</b>: cada bloco é uma matéria com data, veículo, pasta e o link original.</li>",
        "<li><b>Pastas</b>: cada secretaria aparece quando a matéria cita a pasta (nome oficial, sigla ou termo próprio) ou dois temas da área.</li>",
        "<li><b>Escopo</b>: “governo do Estado” é o que trata do Executivo; “outras instituições” é ALMT, câmaras e prefeituras; “geral MT” é notícia de interesse geral do estado.</li>",
        "<li><b>Governador e interino</b>: quando o texto cita o governador ou quem assumiu interinamente, a notícia entra também nessas seções.</li>",
        "<li><b>Cobertura</b>: a porcentagem indica quanto do material do Governo do Estado foi atribuída a alguma pasta — o restante é assunto que atravessa a máquina.</li>",
        "</ol></section>",
    ]

    # resumo por pasta
    partes.append("<h2>Resumo por pasta</h2><table><thead><tr><th>Pasta</th><th>Notícias</th>"
                 "<th>Part. do Governo</th><th>Titular</th></tr></thead><tbody>")
    titulares = {s["sigla"]: s.get("titular", "") for s in seed.get("secretarias", []) + seed.get("autarquias", [])}
    total_governo = max(1, resumo["do_governo_do_estado"])
    for sigla, lista in sorted(por_pasta.items(), key=lambda par: -len(par[1])):
        partes.append(
            f"<tr><td><b>{html.escape(sigla)}</b></td><td>{len(lista)}</td>"
            f"<td>{100*len(lista)/total_governo:.1f}%</td>"
            f"<td>{html.escape(titulares.get(sigla, '—'))}</td></tr>"
        )
    partes.append("</tbody></table>")

    # por pasta
    partes.append("<h2>Por secretaria</h2>")
    for sigla, lista in sorted(por_pasta.items(), key=lambda par: -len(par[1])):
        nome_pasta = next(
            (s.get("nome", "") for s in seed.get("secretarias", []) + seed.get("autarquias", []) if s.get("sigla") == sigla),
            sigla,
        )
        partes.append(f"<h3>{html.escape(sigla)} — {html.escape(nome_pasta)} ({len(lista)})</h3>")
        for item in lista[:25]:
            partes.append(_html_linha(item))
        if len(lista) > 25:
            partes.append(f"<p style='font-size:8pt;color:#64748b'>… e mais {len(lista)-25} (veja a lista completa).</p>")

    # governador / interino
    partes.append(f"<h2>Governador — {html.escape(governador)}</h2>")
    for item in do_governador[:30]:
        partes.append(_html_linha(item))
    partes.append(f"<h2>Governador interino — {html.escape(interino)}</h2>")
    partes.append("<p><span class='selo'>Cargo por ausência — o bite só vale no período em que exerce.</span></p>")
    for item in do_interino[:20]:
        partes.append(_html_linha(item))

    # lista completa
    partes.append("<h2>Lista completa</h2><table><thead><tr><th>Data</th><th>Título</th><th>Veículo</th>"
                 "<th>Pasta</th><th>Escopo</th><th>Link</th></tr></thead><tbody>")
    for item in itens:
        partes.append(
            "<tr>"
            f"<td>{html.escape(_data(item))}</td>"
            f"<td>{html.escape(_titulo(item))}</td>"
            f"<td>{html.escape(item.get('veiculo') or '—')}</td>"
            f"<td>{html.escape(', '.join(item.get('siglas') or []) or 'geral')}</td>"
            f"<td>{html.escape(item.get('escopo') or '')}</td>"
            f"<td><a href='{html.escape(item.get('url') or '')}'>abrir</a></td>"
            "</tr>"
        )
    partes.append("</tbody></table>")

    # contexto
    partes.append("<h2>Contexto de Mato Grosso (outras instituições)</h2>")
    partes.append("<p>Notícias de ALMT, câmaras, prefeituras e do estado em geral — "
                  "fora do Executivo estadual. Listadas para transparência do recorte.</p>")
    for item in contexto[:40]:
        partes.append(_html_linha(item))

    partes.append(
        "<div class='rodape'>"
        "Gerado localmente (sem API paga) em "
        + datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
        + ". Fontes: RSS oficial do portal do Governo de MT (portal.mt.gov.br), "
        "agregador Google News (janela de 60 dias) e sites oficiais de cada secretaria. "
        "Classificação por pasta: dicionário oficial de secretarias, revisado pelo dono "
        "em 24/11/2026. Este material é informativo e não substitui apuração."
        "</div></body></html>"
    )
    return "".join(partes)


def gerar_xlsx(itens: list[dict], seed: dict, resumo: dict, destino: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    cab = Font(bold=True, color="FFFFFF")
    fundo = PatternFill("solid", fgColor="1E3A5F")

    def cabecalho(ws, titulos: list[str]) -> None:
        ws.append(titulos)
        for celula in ws[1]:
            celula.font = cab
            celula.fill = fundo
            celula.alignment = Alignment(vertical="center")

    # Resumo
    ws = wb.active
    ws.title = "Resumo"
    cabecalho(ws, ["Indicador", "Valor"])
    linhas = [
        ("Notícias coletadas", resumo["total"]),
        ("Período — de", resumo["periodo"]["de"]),
        ("Período — até", resumo["periodo"]["ate"]),
        ("Sobre o Governo do Estado", resumo["do_governo_do_estado"]),
        ("Outras instituições de MT", resumo["por_escopo"].get("instituicoes-mt", 0)),
        ("Notícia geral de MT", resumo["por_escopo"].get("geral-mt", 0)),
        ("Com pasta atribuída", resumo["com_secretaria"]),
        ("Cobertura de pasta (%)", resumo["cobertura_no_escopo_do_governo"]),
        ("Citando o governador", resumo["por_alvo"].get("governador", 0)),
        ("Citando o interino", resumo["por_alvo"].get("interino", 0)),
    ]
    for linha in linhas:
        ws.append(list(linha))
    ws.append([])
    cabecalho(ws, ["Pasta", "Notícias", "Titular"])
    titulares = {s["sigla"]: s.get("titular", "") for s in seed.get("secretarias", []) + seed.get("autarquias", [])}
    contagem = Counter()
    for item in itens:
        for sigla in item.get("siglas") or []:
            contagem[sigla] += 1
    for sigla, n in contagem.most_common():
        ws.append([sigla, n, titulares.get(sigla, "")])

    # Por secretaria (uma aba por pasta)
    por_pasta: dict[str, list[dict]] = defaultdict(list)
    for item in itens:
        if item.get("escopo") != "governo-estado":
            continue
        for sigla in item.get("siglas") or []:
            if sigla:
                por_pasta[sigla].append(item)
    for sigla, lista in sorted(por_pasta.items()):
        ws = wb.create_sheet(sigla[:31])
        cabecalho(ws, ["Data", "Título", "Veículo", "Alvos", "Motivo", "Link"])
        for item in lista:
            ws.append(
                [
                    _data(item),
                    _titulo(item),
                    item.get("veiculo", ""),
                    ", ".join(item.get("alvos") or []),
                    "; ".join(
                        f"{k}: {', '.join(v)}" for k, v in (item.get("motivo_secretaria") or {}).items()
                    ),
                    item.get("url", ""),
                ]
            )

    # Governador / interino
    for chave, titulo_col in (("governador", "Governador"), ("interino", "Interino")):
        ws = wb.create_sheet(titulo_col)
        cabecalho(ws, ["Data", "Título", "Veículo", "Pasta", "Link"])
        for item in [i for i in itens if chave in (i.get("alvos") or [])]:
            ws.append(
                [
                    _data(item),
                    _titulo(item),
                    item.get("veiculo", ""),
                    ", ".join(item.get("siglas") or []) or "geral",
                    item.get("url", ""),
                ]
            )

    # Lista completa
    ws = wb.create_sheet("Lista completa")
    cabecalho(ws, ["Data", "Título", "Veículo", "Pasta", "Escopo", "Alvos", "Link"])
    for item in itens:
        ws.append(
            [
                _data(item),
                _titulo(item),
                item.get("veiculo", ""),
                ", ".join(item.get("siglas") or []) or "geral",
                item.get("escopo", ""),
                ", ".join(item.get("alvos") or []),
                item.get("url", ""),
            ]
        )

    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for coluna, largura in zip("ABCDEFG", (12, 62, 26, 14, 18, 40, 40)):
            ws.column_dimensions[coluna].width = largura
    wb.save(destino)


def gerar_csv(itens: list[dict], destino: Path) -> None:
    with destino.open("w", newline="", encoding="utf-8-sig") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(
            ["data", "titulo", "veiculo", "pasta", "siglas", "escopo", "alvos", "confianca", "url"]
        )
        for item in itens:
            escritor.writerow(
                [
                    _data(item),
                    _titulo(item),
                    item.get("veiculo", ""),
                    ", ".join(item.get("secretarias") or []),
                    ", ".join(item.get("siglas") or []),
                    item.get("escopo", ""),
                    ", ".join(item.get("alvos") or []),
                    item.get("confianca_secretaria", ""),
                    item.get("url", ""),
                ]
            )


def gerar_pdf(conteudo_html: str, destino: Path) -> None:
    from playwright.sync_api import sync_playwright

    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
        pagina = navegador.new_page()
        pagina.set_content(conteudo_html, wait_until="load")
        pagina.pdf(path=str(destino), format="A4", print_background=True)
        navegador.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Relatorio do clipping do Governo de MT.")
    parser.add_argument("--jsonl", default="")
    parser.add_argument("--saida", default=str(PASTA_PADRAO))
    args = parser.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    pasta = Path(args.saida)
    if args.jsonl:
        arquivo = Path(args.jsonl)
    else:
        arquivos = sorted(pasta.glob("noticias-*.jsonl"))
        if not arquivos:
            logger.error("Nenhuma coleta encontrada em %s. Rode coletar_governo_mt.py antes.", pasta)
            return 1
        arquivo = arquivos[-1]

    itens = carregar_itens(arquivo)
    if not itens:
        logger.error("Coleta vazia.")
        return 1

    # resumo (recalculado aqui para bater com o relatorio)
    por_escopo = Counter(i.get("escopo", "geral-mt") for i in itens)
    por_alvo = Counter(a for i in itens for a in (i.get("alvos") or []))
    sem_pasta = sum(1 for i in itens if i.get("secretarias") == ["geral-governo"])
    datas = [i["data"] for i in itens if i.get("data")]
    resumo = {
        "total": len(itens),
        "periodo": {
            "de": min(datas).isoformat() if datas else None,
            "ate": max(datas).isoformat() if datas else None,
        },
        "por_escopo": dict(por_escopo),
        "do_governo_do_estado": por_escopo.get("governo-estado", 0),
        "com_secretaria": len(itens) - sem_pasta,
        "sem_secretaria": sem_pasta,
        "cobertura_no_escopo_do_governo": round(
            100 * (len(itens) - sem_pasta) / max(1, por_escopo.get("governo-estado", 1)), 1
        ),
        "por_alvo": dict(por_alvo),
    }

    marca = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    html_gerado = construir_html(itens, seed, resumo)
    (pasta / f"relatorio-governo-mt-{marca}.html").write_text(html_gerado, encoding="utf-8")
    gerar_xlsx(itens, seed, resumo, pasta / f"noticias-governo-mt-{marca}.xlsx")
    gerar_csv(itens, pasta / f"noticias-governo-mt-{marca}.csv")
    gerar_pdf(html_gerado, pasta / f"noticias-governo-mt-{marca}.pdf")

    print("=== RELATORIO DO GOVERNO DE MT ===")
    print(f"notícias: {resumo['total']} | do Governo do Estado: {resumo['do_governo_do_estado']}")
    print(f"com pasta: {resumo['com_secretaria']} ({resumo['cobertura_no_escopo_do_governo']}% do escopo do governo)")
    print(f"governador: {resumo['por_alvo'].get('governador', 0)} | interino: {resumo['por_alvo'].get('interino', 0)}")
    for arquivo in sorted(pasta.glob(f"noticias-governo-mt-{marca}.*")):
        print(f"  {arquivo.name} ({arquivo.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
