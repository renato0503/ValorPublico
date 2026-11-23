"""Entrega de alertas acionaveis por e-mail (SMTP) e/ou webhook (WhatsApp/Make).

Fecha o principal gap do servico: ate aqui os alertas existiam apenas no
painel. Este script:

  1. le os alertas publicados em `alertas/<escopo>` (gerados por
     `atualizar_radares.py`);
  2. filtra por nivel minimo e janela (padrao: alertas de hoje);
  3. deduplica pelo `chave` do alerta usando o estado em `alertas_enviados`;
  4. envia por SMTP (e-mail) e/ou por webhook (WhatsApp/Zapier/Make);
  5. registra o que foi enviado (para nao repetir).

Nao envia nada se nao houver destinatario configurado - o script apenas
registra o estado quando `--dry-run` e usado.

Uso:
    python scripts/enviar_alertas.py --dry-run
    python scripts/enviar_alertas.py --nivel critico --periodo hoje
    python scripts/enviar_alertas.py --forcar      # reenvia tudo
"""

import json
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (  # noqa: E402
    ALERTA_DESTINATARIOS,
    ALERTA_NIVEL_MINIMO,
    ALERTA_WEBHOOK_SECRET,
    ALERTA_WEBHOOK_URL,
    EMAIL_FROM,
    EMAIL_PARA,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_TLS,
    SMTP_USER,
)
from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.quota import main_com_cota  # noqa: E402

logger = get_logger(__name__)

COLECAO_ESTADO = "alertas_enviados"
ORDEM_NIVEIS = {"info": 0, "atencao": 1, "alto": 2, "critico": 3}


def _periodo_chave(periodo: str) -> str:
    return f"periodo-{periodo}"


def _nivel_minimo(nivel: str) -> str:
    atual = ALERTA_NIVEL_MINIMO or "alto"
    if ORDEM_NIVEIS.get(nivel, 0) >= ORDEM_NIVEIS.get(atual, 2):
        return atual
    return atual


def _texto_alerta(alerta: dict) -> str:
    linhas = [
        f"[{str(alerta.get('nivel', 'info')).upper()}] {alerta.get('titulo', '')}",
        f"Detalhe: {alerta.get('detalhe', '')}",
    ]
    if alerta.get("veiculo"):
        linhas.append(f"Fonte: {alerta['veiculo']}")
    if alerta.get("url"):
        linhas.append(f"Link: {alerta['url']}")
    if alerta.get("acao_sugerida"):
        linhas.append(f"Acao sugerida: {alerta['acao_sugerida']}")
    return "\n".join(linhas)


def _html_alerta(alerta: dict) -> str:
    cor = {"critico": "#dc2626", "alto": "#d97706", "atencao": "#2563eb", "info": "#64748b"}.get(
        alerta.get("nivel", "info"), "#64748b"
    )
    return (
        f'<div style="border-left:4px solid {cor};padding:10px 14px;margin:8px 0;'
        f'background:#f8fafc;font-family:Segoe UI,Arial,sans-serif">'
        f'<div style="font-weight:700;color:#0f172a">{alerta.get("titulo", "")}</div>'
        f'<div style="font-size:13px;color:#334155;margin-top:4px">{alerta.get("detalhe", "")}</div>'
        f'<div style="font-size:12px;color:#64748b;margin-top:6px">'
        f'{alerta.get("veiculo", "")} · R$ {float(alerta.get("valor_estimado") or 0):,.0f}'
        + (f' · <a href="{alerta["url"]}">abrir</a>' if alerta.get("url") else "")
        + (
            f'<div style="font-size:12px;color:{cor};margin-top:4px">→ {alerta.get("acao_sugerida", "")}</div>'
            if alerta.get("acao_sugerida")
            else ""
        )
        + "</div></div>"
    )


def enviar_email(destinatarios: list[str], assunto: str, corpo_html: str, corpo_texto: str) -> bool:
    if not (SMTP_HOST and destinatarios and EMAIL_FROM):
        return False
    try:
        mensagem = EmailMessage()
        mensagem["Subject"] = assunto
        mensagem["From"] = EMAIL_FROM
        mensagem["To"] = ", ".join(destinatarios)
        mensagem.set_content(corpo_texto)
        mensagem.add_alternative(corpo_html, subtype="html")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as servidor:
            if SMTP_TLS:
                servidor.starttls()
            if SMTP_USER:
                servidor.login(SMTP_USER, SMTP_PASSWORD)
            servidor.send_message(mensagem)
        logger.info("E-mail de alertas enviado para %s.", ", ".join(destinatarios))
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao enviar e-mail de alertas: %s", e)
        return False


def enviar_webhook(payload: dict) -> bool:
    if not ALERTA_WEBHOOK_URL:
        return False
    try:
        corpo = json.dumps(payload, default=str).encode("utf-8")
        cabecalhos = {"Content-Type": "application/json"}
        if ALERTA_WEBHOOK_SECRET:
            cabecalhos["X-Alerta-Secret"] = ALERTA_WEBHOOK_SECRET
        requisicao = urllib.request.Request(
            ALERTA_WEBHOOK_URL, data=corpo, headers=cabecalhos, method="POST"
        )
        with urllib.request.urlopen(requisicao, timeout=20) as resposta:
            logger.info("Webhook de alertas disparado (%s).", resposta.status)
            return True
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao disparar webhook de alertas: %s", e)
        return False


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    forcar = "--forcar" in sys.argv
    periodo = "hoje"
    nivel_minimo = ALERTA_NIVEL_MINIMO or "alto"
    for arg in sys.argv:
        if arg.startswith("--periodo="):
            periodo = arg.split("=", 1)[1]
        if arg.startswith("--nivel="):
            nivel_minimo = arg.split("=", 1)[1]

    if ORDEM_NIVEIS.get(nivel_minimo, 2) < ORDEM_NIVEIS.get("alto", 2):
        nivel_minimo = "alto"

    db = init_firebase()
    enviados_ref = db.collection(COLECAO_ESTADO).document("estado")
    enviados = (enviados_ref.get().to_dict() or {}).get("enviados", {}) if not forcar else {}

    total_alertas = 0
    total_enviados = 0
    escopos = []

    for doc in db.collection("alertas").stream():
        dados = doc.to_dict() or {}
        bloco = dados.get(_periodo_chave(periodo)) or {}
        itens = (bloco.get("alertas") or {}).get("itens") or []
        if not itens:
            continue
        escopo = dados.get("escopo") or {"nome": doc.id, "chave": doc.id}
        selecionados = [
            a for a in itens
            if ORDEM_NIVEIS.get(a.get("nivel", "info"), 0) >= ORDEM_NIVEIS.get(nivel_minimo, 2)
            and (forcar or a.get("chave") not in enviados)
        ]
        if not selecionados:
            continue
        escopos.append((escopo, selecionados))
        total_alertas += len(selecionados)

    if dry_run:
        for escopo, itens in escopos:
            print(f"[dry-run] {escopo.get('nome')} ({escopo.get('chave')}): {len(itens)} alertas")
            for alerta in itens[:5]:
                print(f"   - [{alerta.get('nivel')}] {alerta.get('titulo')}")
        logger.info("Dry-run: %d alertas em %d escopos (nada enviado).", total_alertas, len(escopos))
        return

    for escopo, itens in escopos:
        assunto = f"[Alertas] {escopo.get('nome')} - {periodo}"
        corpo_texto = "\n\n".join(_texto_alerta(a) for a in itens)
        corpo_html = (
            "<html><body style='font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9'>"
            "<div style='max-width:640px;margin:0 auto;background:#fff;padding:20px'>"
            f"<h2 style='margin:0 0 4px;font-size:18px'>{escopo.get('nome')}</h2>"
            f"<p style='margin:0 0 12px;color:#64748b;font-size:13px'>{len(itens)} alertas - {periodo}</p>"
            + "".join(_html_alerta(a) for a in itens)
            + "</div></body></html>"
        )
        enviados_ok = []
        if EMAIL_PARA or ALERTA_DESTINATARIOS:
            if enviar_email(EMAIL_PARA or ALERTA_DESTINATARIOS, assunto, corpo_html, corpo_texto):
                enviados_ok.append("email")
        if enviar_webhook({
            "escopo": escopo,
            "periodo": periodo,
            "nivel_minimo": nivel_minimo,
            "total": len(itens),
            "alertas": itens,
            "texto": corpo_texto,
            "html": corpo_html,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        }):
            enviados_ok.append("webhook")

        if enviados_ok:
            for alerta in itens:
                enviados[alerta.get("chave", "")] = {
                    "enviado_em": datetime.now(timezone.utc).isoformat(),
                    "canais": enviados_ok,
                    "escopo": escopo.get("chave"),
                }
                total_enviados += 1

    enviados_ref.set({
        "enviados": enviados,
        "atualizado_em": datetime.now(timezone.utc),
    }, merge=True)

    logger.info(
        "Alertas: %d novos encontrados, %d enviados, %d escopos.",
        total_alertas, total_enviados, len(escopos),
    )


if __name__ == "__main__":
    main_com_cota(main, "enviar_alertas")

