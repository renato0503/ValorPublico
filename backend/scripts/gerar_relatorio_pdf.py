"""Gera um relatorio em PDF (reportlab) com os dados agregados do dashboard.

Le as metricas prontas do Firestore (`metricas/geral`, ou por cidade/agente)
e produz um PDF brandado com KPIs, distribuicao de sentimento, share de midia,
temas, top veiculos e somatorios de espaco/valor. Alternativa a exportacao via
impressao do navegador (`@media print`).

Uso:
    python scripts/gerar_relatorio_pdf.py                      # metricas/geral
    python scripts/gerar_relatorio_pdf.py --agente <id>
    python scripts/gerar_relatorio_pdf.py --cidade cuiaba
    python scripts/gerar_relatorio_pdf.py --saida relatorio.pdf
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


def _formatar_numero(n):
    return f"{int(round(n or 0)):,}".replace(",", ".")


def _formatar_valor(n):
    return f"R$ {float(n or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_data(v) -> str:
    if not v:
        return "—"
    try:
        if hasattr(v, "to_pydatetime"):
            v = v.to_pydatetime()
        return v.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"


def _resolver_fonte(db, args) -> tuple[str, dict]:
    if args.agente:
        doc = db.collection("metricas_por_agente").document(args.agente).get()
        return f"Relatório por parlamentar · {args.agente}", (doc.to_dict() if doc.exists else {})
    if args.cidade:
        doc = db.collection("metricas_por_cidade").document(args.cidade).get()
        return f"Relatório por cidade · {args.cidade}", (doc.to_dict() if doc.exists else {})
    doc = db.collection("metricas").document("geral").get()
    return "Relatório Executivo", (doc.to_dict() if doc.exists else {})


def _tabela(dados, cabecalhos, larguras=None, total_cols=2):
    rows = [cabecalhos] + dados
    t = Table(rows, colWidths=larguras)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ALIGN", (total_cols, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _espaco_texto(espaco: dict) -> str:
    espaco = espaco or {}
    partes = []
    if espaco.get("caracteres"):
        partes.append(f"{_formatar_numero(espaco['caracteres'])} caracteres (site)")
    if espaco.get("duracao_seg"):
        partes.append(f"{_formatar_numero(espaco['duracao_seg'] // 60)} min (TV/rádio)")
    if espaco.get("cm2"):
        partes.append(f"{_formatar_numero(espaco['cm2'])} cm² (impresso)")
    return " · ".join(partes) if partes else "—"


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera relatorio PDF (reportlab).")
    parser.add_argument("--agente", default="", help="ID do agente (metricas_por_agente).")
    parser.add_argument("--cidade", default="", help="Slug da cidade (metricas_por_cidade).")
    parser.add_argument("--saida", default="", help="Caminho do PDF (padrao: data/export/relatorio.pdf).")
    args = parser.parse_args()

    db = init_firebase()
    titulo, dados = _resolver_fonte(db, args)
    if not dados:
        logger.error("Sem dados para a fonte selecionada.")
        sys.exit(1)

    saida = Path(args.saida) if args.saida.strip() else settings.DATA_DIR / "export" / "relatorio.pdf"
    saida.parent.mkdir(parents=True, exist_ok=True)

    estilos = getSampleStyleSheet()
    titulo_estilo = ParagraphStyle(
        "Titulo", parent=estilos["Title"], fontSize=20, textColor=colors.HexColor("#0f172a")
    )
    subtitulo = ParagraphStyle(
        "Sub", parent=estilos["Normal"], fontSize=10, textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    secao = ParagraphStyle(
        "Sec", parent=estilos["Heading2"], fontSize=12, textColor=colors.HexColor("#1e293b"),
        spaceBefore=10, spaceAfter=6,
    )

    doc = SimpleDocTemplate(
        str(saida), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"{titulo} · ValorPúblico",
        author="ValorPúblico",
    )

    agora = datetime.now(timezone.utc)
    elementos = []
    elementos.append(Paragraph("ValorPúblico — BI & Monitoramento de Mídia", titulo_estilo))
    elementos.append(Paragraph(
        f"{titulo} · Gerado em {agora.strftime('%d/%m/%Y %H:%M')} (UTC) · "
        f"Atualização: {_formatar_data(dados.get('atualizado_em'))}",
        subtitulo,
    ))
    elementos.append(Spacer(1, 4))

    # KPIs
    elementos.append(Paragraph("Indicadores principais", secao))
    kpis = [
        ["Fontes", "Audiência", "Valoração (R$)", "Clippings"],
        [
            _formatar_numero(dados.get("total_veiculos")),
            _formatar_numero(dados.get("audiencia_total")),
            _formatar_valor(dados.get("valoracao_total")),
            _formatar_numero(dados.get("total_clippings")),
        ],
    ]
    elementos.append(_tabela(kpis[1:], kpis[0], larguras=[45 * mm] * 4, total_cols=4))
    elementos.append(Spacer(1, 2))
    elementos.append(Paragraph(
        f"Espaço total: {_espaco_texto(dados.get('espaco_total'))}",
        subtitulo,
    ))

    # Sentimento
    elementos.append(Paragraph("Sentimento", secao))
    sent = dados.get("distribuicao_sentimento", {})
    total_sent = sum(sent.values()) or 1
    linhas_sent = [
        [nome.title(), _formatar_numero(qtd), f"{round(100 * qtd / total_sent, 1)}%"]
        for nome, qtd in sorted(sent.items(), key=lambda kv: -kv[1])
    ]
    elementos.append(_tabela(linhas_sent, ["Sentimento", "Menções", "%"], larguras=[60 * mm, 40 * mm, 40 * mm]))

    # Share de mídia
    elementos.append(Paragraph("Share de Mídia", secao))
    categorias = dados.get("distribuicao_categorias", {})
    total_cat = sum(categorias.values()) or 1
    linhas_cat = [
        [nome, _formatar_numero(qtd), f"{round(100 * qtd / total_cat, 1)}%"]
        for nome, qtd in sorted(categorias.items(), key=lambda kv: -kv[1])
    ]
    if linhas_cat:
        elementos.append(_tabela(linhas_cat, ["Categoria", "Menções", "%"], larguras=[60 * mm, 40 * mm, 40 * mm]))

    # Temas
    elementos.append(Paragraph("Temas em Destaque", secao))
    temas = dados.get("distribuicao_temas", {})
    linhas_temas = [[nome, _formatar_numero(qtd)] for nome, qtd in list(temas.items())[:16]]
    if linhas_temas:
        elementos.append(_tabela(linhas_temas, ["Tema", "Menções"], larguras=[100 * mm, 40 * mm]))

    # Top veículos
    elementos.append(Paragraph("Top Fontes Relevantes", secao))
    top = dados.get("top_veiculos", [])[:15]
    linhas_top = [
        [v.get("nome", ""), v.get("categoria_midia", ""), _formatar_numero(v.get("clippings")),
         _formatar_numero(v.get("audiencia")), _formatar_valor(v.get("valor_estimado"))]
        for v in top
    ]
    if linhas_top:
        elementos.append(_tabela(
            linhas_top,
            ["Fonte", "Tipo", "Clippings", "Audiência", "Valor (R$)"],
            larguras=[52 * mm, 26 * mm, 22 * mm, 26 * mm, 30 * mm],
            total_cols=3,
        ))

    doc.build(elementos)
    logger.info("Relatório PDF gerado -> %s", saida)
    print(f"Relatório gerado: {saida}")


if __name__ == "__main__":
    main()