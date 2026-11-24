"""PDF do relatorio semanal (plano 10 §4.1): o **mesmo HTML** impresso pelo Playwright.

Um unico desenho para app e relatorio. A pagina 2 e sempre "Como ler este
relatorio" (plano 17 §4.4).

Uso (a partir de `backend/`):
    python scripts/semanal/pdf.py --escopo agente-adevair-cabral
    python scripts/semanal/pdf.py --todos
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.processing.textos_graficos import carimbo
from config import settings

logger = get_logger(__name__)

CSS = """
  @page { size: A4; margin: 18mm; }
  * { box-sizing: border-box; }
  body { font-family: "Inter", "Helvetica Neue", Arial, sans-serif; color: #0f172a;
         font-size: 10.5pt; line-height: 1.55; }
  h1 { font-size: 20pt; margin: 0 0 2mm; }
  h2 { font-size: 13pt; margin: 8mm 0 2mm; padding-bottom: 1mm;
       border-bottom: 1px solid #cbd5e1; }
  h3 { font-size: 11pt; margin: 4mm 0 1mm; }
  .capa { padding: 12mm 0 6mm; border-bottom: 3px double #1e3a5f; }
  .capa .eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: 8.5pt; color: #475569; }
  .capa .numeros { display: flex; gap: 8mm; margin-top: 6mm; }
  .capa .numero { flex: 1; }
  .capa .numero b { display: block; font-size: 18pt; }
  .capa .numero span { font-size: 8.5pt; color: #475569; }
  .como-ler ol { margin: 2mm 0 0 5mm; }
  .como-ler li { margin-bottom: 1.5mm; }
  .classe { border: 1px solid #cbd5e1; border-radius: 2mm; padding: 3mm; margin-bottom: 3mm;
            page-break-inside: avoid; }
  .classe-cab { display: flex; justify-content: space-between; align-items: baseline; }
  .classe h3 { margin: 0; }
  .pct { font-size: 13pt; font-weight: 700; }
  .formas { margin: 2mm 0 0; font-size: 9pt; color: #334155; }
  .leitura { background: #f1f5f9; border-left: 3px solid #2563eb; padding: 2.5mm 3mm;
             margin-top: 2mm; font-size: 9.5pt; }
  .rodape { margin-top: 8mm; padding-top: 2mm; border-top: 1px solid #cbd5e1;
            font-size: 8pt; color: #64748b; }
  .selo { display: inline-block; border: 1px solid #a16207; background: #fef3c7;
          color: #854d0e; padding: 1mm 2mm; border-radius: 1mm; font-size: 8.5pt; }
  .selo-ia { border-color: #7c3aed; background: #ede9fe; color: #5b21b6; }
  pre { white-space: pre-wrap; font-family: inherit; font-size: 10pt; }
"""


def html_do_relatorio(relatorio: dict, discurso: dict | None) -> str:
    escopo = relatorio.get("escopo", "")
    rotulo = relatorio.get("rotulo") or escopo
    semana = relatorio.get("semana", "")
    est = relatorio.get("estatisticas", {})
    classes = relatorio.get("chd", {}).get("classes", [])
    textos = relatorio.get("textos", {})

    dominante = classes[0]["rotulo"] if classes else "—"
    partes = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>Relatório da semana — {rotulo}</title><style>{CSS}</style></head><body>",
        # capa
        "<section class='capa'>",
        f"<p class='eyebrow'>{carimbo()} · Semana {semana}</p>",
        f"<h1>{rotulo}</h1>",
        "<div class='numeros'>",
        f"<div class='numero'><b>{est.get('textos', 0)}</b><span>textos analisados</span></div>",
        f"<div class='numero'><b>{est.get('st', 0)}</b><span>segmentos de texto</span></div>",
        f"<div class='numero'><b>{len(classes)}</b><span>grupos de assuntos</span></div>",
        f"<div class='numero'><b>{dominante}</b><span>grupo dominante</span></div>",
        "</div></section>",
        # como ler
        "<section class='como-ler'><h2>Como ler este relatório</h2><ol>",
        "<li><b>Grupos de assuntos</b>: os textos da semana são agrupados pelas palavras que usam em comum. Cada grupo é um assunto.</li>",
        "<li><b>Porcentagem</b>: quanto do material da semana está naquele grupo. Grupo maior = assunto mais presente.</li>",
        "<li><b>χ² (qui-quadrado)</b>: o quanto uma palavra é típica do grupo. Quanto maior, mais aquela palavra caracteriza o assunto.</li>",
        "<li><b>Leitura do momento</b>: um texto explica, em linguagem simples, o que aquele gráfico mostra nesta semana.</li>",
        "<li><b>Fontes</b>: cada afirmação do discurso aponta de onde veio (veículo e data).</li>",
        "</ol></section>",
    ]

    # resumo
    if textos.get("resumo"):
        partes.append("<h2>Resumo da semana</h2>")
        partes.append(f"<p>{textos['resumo']}</p>")

    # mundos lexicais
    partes.append("<h2>Mundos lexicais (grupos de assuntos)</h2>")
    if textos.get("chd"):
        partes.append(f"<div class='leitura'>{textos['chd']}</div>")
    for classe in classes[:8]:
        formas = ", ".join(f"{f['f']} ({f['chi2']:.0f})" for f in classe.get("formas", [])[:8])
        partes.append(
            "<div class='classe'>"
            "<div class='classe-cab'>"
            f"<h3>{classe.get('rotulo', '')}</h3>"
            f"<span class='pct'>{classe.get('pct', 0):.0f}%</span>"
            "</div>"
            f"<p class='formas'>{formas}</p>"
            "</div>"
        )

    # o que mudou
    if textos.get("especificidades"):
        partes.append("<h2>O que mudou</h2>")
        partes.append(f"<p>{textos['especificidades']}</p>")

    # discurso
    if discurso and discurso.get("variantes"):
        partes.append("<h2>Discurso da semana</h2>")
        partes.append("<p><span class='selo selo-ia'>Rascunho gerado por IA — revisar antes de usar</span></p>")
        for variante in discurso["variantes"]:
            partes.append(f"<h3>Variante {variante['id']} — {variante.get('angulo', '')}</h3>")
            texto = (variante.get("tribuna") or "").strip()
            partes.append(f"<pre>{texto[:4000]}</pre>")
            if variante.get("fontes"):
                partes.append(
                    "<p class='formas'>Fontes citadas: "
                    + "; ".join(variante["fontes"][:10])
                    + "</p>"
                )
        if discurso.get("nivel") == "agente":
            partes.append("<p><span class='selo'>Simulação (hipótese) — não é pesquisa</span></p>")

    # rodape
    partes.append(
        "<div class='rodape'>"
        f"Fonte dos dados: clippings monitorados dos agentes públicos ({est.get('textos', 0)} textos). "
        f"Gerado em {carimbo()}. "
        "Método: classificação hierárquica descendente de Reinert (pacote rainette) sobre segmentos de texto. "
        "Este relatório é um apoio à decisão: as afirmações do discurso devem ser conferidas na fonte."
        "</div></body></html>"
    )
    return "".join(partes)


def gerar_pdf(html: str, destino: Path) -> bool:
    """Imprime o HTML em PDF com o Playwright (Chromium)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playwright indisponivel: %s", exc)
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
        pagina = navegador.new_page()
        pagina.set_content(html, wait_until="load")
        pagina.pdf(path=str(destino), format="A4", print_background=True)
        navegador.close()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF do relatorio semanal.")
    parser.add_argument("--escopo", default="")
    parser.add_argument("--todos", action="store_true")
    args = parser.parse_args()

    semana = datetime.now(timezone.utc).strftime("%G-W%V")
    pasta = Path(settings.DATA_DIR) / "semanal" / semana
    if not pasta.exists():
        logger.error("Sem dados da semana: rode scripts/semanal/relatorio.py antes.")
        return 1

    arquivos = sorted(pasta.glob("relatorio-*.json"))
    if args.escopo:
        arquivos = [pasta / f"relatorio-{args.escopo}.json"]
        if not arquivos[0].exists():
            logger.error("Relatorio nao encontrado: %s", arquivos[0])
            return 1

    total = 0
    for arquivo in arquivos:
        relatorio = json.loads(arquivo.read_text(encoding="utf-8"))
        escopo = relatorio.get("escopo", arquivo.stem)
        discurso_path = pasta / f"discurso-{escopo}.json"
        discurso = json.loads(discurso_path.read_text(encoding="utf-8")) if discurso_path.exists() else None
        html = html_do_relatorio(relatorio, discurso)
        (pasta / f"relatorio-{escopo}.html").write_text(html, encoding="utf-8")
        destino = pasta / f"{escopo}.pdf"
        if gerar_pdf(html, destino):
            logger.info("PDF: %s (%.0f KB)", destino, destino.stat().st_size / 1024)
            total += 1
    logger.info("PDFs gerados: %d", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
