"""Gera a newsletter consolidada do clipping (padrao "newsletter" das plataformas).

Entrega em tres formatos:
  - HTML  (e-mail / PDF): tabela com as principais mencoes, destaque do
           trecho citado, sentimento, valor e link da fonte;
  - texto (WhatsApp/Telegram): mensagem curta, direto ao ponto;
  - JSON  (webhook / API): payload estruturado.

Grava em `newsletters/<escopo>` e, se `NEWSLETTER_WEBHOOK` estiver configurado,
dispara o payload para o webhook (Make/Zapier/n8n) que encaminha para e-mail
ou WhatsApp.

Uso:
    python scripts/gerar_newsletter.py
    python scripts/gerar_newsletter.py --periodos 7d --apenas-escopos geral
    python scripts/gerar_newsletter.py --enviar
"""

import html
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (  # noqa: E402
    COLLECTION_NEWSLETTERS,
    NEWSLETTER_ASSINATURA,
    NEWSLETTER_ENABLED,
    NEWSLETTER_MAX_ITENS,
    NEWSLETTER_WEBHOOK,
)
from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.quota import main_com_cota  # noqa: E402
from scripts.atualizar_metricas import coletar_clippings, slugify_cidade  # noqa: E402

logger = get_logger(__name__)

PERIODOS = {"hoje": 0, "7d": 7, "15d": 15, "30d": 30}


def _dentro(dt, dias: int) -> bool:
    if dt is None:
        return False
    try:
        hoje = datetime.now(timezone.utc).date()
        data = dt.astimezone(timezone.utc).date() if hasattr(dt, "astimezone") else None
        if data is None:
            from datetime import date as _date

            try:
                data = _date.fromisoformat(str(dt)[:10])
            except ValueError:
                return False
        return 0 <= (hoje - data).days <= dias
    except Exception:  # noqa: BLE001
        return False


def _fmt_data(dt) -> str:
    if not dt:
        return ""
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except AttributeError:
        return str(dt)[:16]


def _veiculo(clipping: dict) -> str:
    metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
    return metadados.get("veiculo") or clipping.get("autor") or "Fonte nao identificada"


def _trecho(clipping: dict) -> str:
    trecho = clipping.get("trecho") or {}
    if isinstance(trecho, dict) and trecho.get("trecho"):
        return trecho["trecho"]
    return (clipping.get("texto_limpo") or "")[:280]


def montar_html(escopo_nome: str, itens: list[dict], periodo_rotulo: str) -> str:
    linhas = []
    for item in itens:
        trecho = html.escape(item["trecho"])
        veiculo = html.escape(item["veiculo"])
        url = html.escape(item["url"] or "#")
        sentiment = html.escape(item["sentimento"])
        cor = {"positivo": "#16a34a", "negativo": "#dc2626", "neutro": "#64748b"}.get(
            sentiment, "#64748b"
        )
        linhas.append(
            f"""
      <tr>
        <td style="padding:12px;border-bottom:1px solid #e2e8f0">
          <div style="font-weight:600;color:#0f172a">{trecho}</div>
          <div style="font-size:12px;color:#64748b;margin-top:6px">
            {veiculo} &middot; {_fmt_data(item['data'])} &middot;
            <span style="color:{cor};font-weight:600">{sentiment}</span>
            &middot; R$ {item['valor']:,.0f}
          </div>
          <a href="{url}" style="font-size:12px;color:#2563eb">abrir materia</a>
        </td>
      </tr>"""
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{html.escape(escopo_nome)} - {html.escape(periodo_rotulo)}</title></head>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:Inter,Segoe UI,Arial,sans-serif">
  <div style="max-width:720px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden">
    <div style="background:#0f172a;color:#fff;padding:20px 24px">
      <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;opacity:.7">
        {html.escape(NEWSLETTER_ASSINATURA)}
      </div>
      <div style="font-size:20px;font-weight:700;margin-top:6px">{html.escape(escopo_nome)}</div>
      <div style="font-size:13px;opacity:.8;margin-top:2px">{html.escape(periodo_rotulo)}</div>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px">{''.join(linhas)}</table>
    <div style="padding:16px 24px;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0">
      Gerado automaticamente em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC.
      Mídia espontânea - valores são estimativas (AVPE) e não representam veiculação contratada.
    </div>
  </div>
</body></html>"""


def montar_texto(escopo_nome: str, itens: list[dict], periodo_rotulo: str) -> str:
    linhas = [
        f"*{escopo_nome}* - {periodo_rotulo}",
        "",
    ]
    for item in itens:
        marcacao = {"positivo": "[+]", "negativo": "[-]", "neutro": "[=]"}.get(
            item["sentimento"], "[=]"
        )
        linhas.append(f"{marcacao} *{item['veiculo']}* - {item['trecho'][:180]}")
        if item["url"]:
            linhas.append(f"    {item['url']}")
    linhas.append("")
    linhas.append(f"Total de mencoes: {len(itens)}")
    return "\n".join(linhas)


def _payload(escopo: dict, chave: str, rotulo: str, itens: list[dict], html_doc: str, texto: str) -> dict:
    return {
        "escopo": escopo,
        "chave": chave,
        "periodo": rotulo,
        "total": len(itens),
        "html": html_doc,
        "texto": texto,
        "itens": itens,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    db = init_firebase()
    if not NEWSLETTER_ENABLED:
        logger.info("Newsletter desabilitada (NEWSLETTER_ENABLED=0).")
        return

    enviar = "--enviar" in sys.argv
    periodos_escolhidos = ["hoje", "7d", "15d", "30d"]
    for arg in sys.argv:
        if arg.startswith("--periodos="):
            periodos_escolhidos = [p for p in arg.split("=", 1)[1].split(",") if p in PERIODOS]
    apenas: set[str] = set()
    for arg in sys.argv:
        if arg.startswith("--apenas-escopos="):
            apenas = {e for e in arg.split("=", 1)[1].split(",") if e}

    clippings = coletar_clippings(db)
    por_cidade: dict[str, list[dict]] = defaultdict(list)
    por_agente: dict[str, list[dict]] = defaultdict(list)
    for clipping in clippings:
        por_cidade[clipping.get("cidade") or "Sem cidade"].append(clipping)
        por_agente[clipping["agente_id"]].append(clipping)

    escopos = [({"tipo": "geral", "chave": "geral", "nome": "Visão geral"}, clippings)]
    for cidade, itens in por_cidade.items():
        slug = slugify_cidade(cidade)
        escopos.append(({"tipo": "cidade", "chave": f"cidade-{slug}", "nome": cidade}, itens))
    for agente_id, itens in por_agente.items():
        nome = itens[0].get("nome_agente") if itens else agente_id
        escopos.append(({"tipo": "agente", "chave": f"agente-{agente_id}", "nome": nome}, itens))

    total_docs = 0
    for escopo, itens in escopos:
        if apenas and escopo["chave"] not in apenas:
            continue
        documento: dict = {"escopo": escopo}
        for chave in periodos_escolhidos:
            dias = PERIODOS[chave]
            if dias == 0:
                hoje = datetime.now(timezone.utc).date().isoformat()
                janela = [c for c in itens if str(c.get("data_publicacao") or "")[:10] == hoje]
            else:
                janela = [c for c in itens if _dentro(c.get("data_publicacao"), dias)]
            janela = sorted(janela, key=lambda c: str(c.get("data_publicacao") or ""), reverse=True)
            selecionados = janela[:NEWSLETTER_MAX_ITENS]

            itens_payload = [
                {
                    "id_clipping": c.get("id_clipping") or "",
                    "trecho": _trecho(c),
                    "veiculo": _veiculo(c),
                    "data": c.get("data_publicacao"),
                    "sentimento": c.get("sentimento", "neutro"),
                    "valor": float(c.get("valor_estimado") or 0.0),
                    "valor_avpe": float(c.get("valor_avpe") or 0.0),
                    "tipo_mencao": c.get("tipo_mencao", ""),
                    "url": c.get("url") or "",
                }
                for c in selecionados
            ]
            rotulo = {
                "hoje": "Hoje", "7d": "Ultimos 7 dias", "15d": "Ultimos 15 dias",
                "30d": "Ultimos 30 dias",
            }[chave]
            html_doc = montar_html(escopo["nome"], itens_payload, rotulo)
            texto = montar_texto(escopo["nome"], itens_payload, rotulo)
            documento[f"periodo-{chave}"] = _payload(
                escopo, escopo["chave"], rotulo, itens_payload, html_doc, texto
            )
            if enviar and NEWSLETTER_WEBHOOK and itens_payload:
                _disparar_webhook(documento[f"periodo-{chave}"])
        documento["gerado_em"] = datetime.now(timezone.utc)
        db.collection(COLLECTION_NEWSLETTERS).document(escopo["chave"]).set(documento, merge=True)
        total_docs += 1

    logger.info("Newsletters geradas: %d escopos.", total_docs)


def _disparar_webhook(payload: dict) -> None:
    try:
        corpo = json.dumps(payload, default=str).encode("utf-8")
        requisicao = urllib.request.Request(
            NEWSLETTER_WEBHOOK,
            data=corpo,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(requisicao, timeout=20) as resposta:
            logger.info("Webhook disparado (%s): %s", payload.get("chave"), resposta.status)
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao disparar webhook da newsletter: %s", e)


if __name__ == "__main__":
    main_com_cota(main, "gerar_newsletter")
