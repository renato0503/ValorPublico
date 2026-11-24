"""Telegram publico (sem login) via `t.me/s/<canal>` (plano 05 §7).

O Telethon (MTProto autenticado) foi arquivado no GitHub e exige login +
numero; nao entra no CI. O jeito oficial e gratuito de ler um canal publico
e a versao "web" do proprio Telegram: `https://t.me/s/<canal>` devolve o HTML
publico com as ultimas ~20 mensagens.

Regras (plano 05 §3): sem login, sem cookies de terceiros, sem CAPTCHA.
Apenas conteudo publico. Autor do post e o canal (nao ha->
comentaristas nao aparecem aqui).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def url_publico(canal: str) -> str:
    """URL publica do canal (`@canal` ou `canal`)."""
    nome = (canal or "").strip().lstrip("@")
    return f"https://t.me/s/{nome}"


def extrair_mensagens(html: str, limite: int = 20) -> list[dict]:
    """Extrai as mensagens publicas do HTML de `t.me/s/<canal>`.

    Cada mensagem: {"id", "texto", "data", "visualizacoes", "url"}.
    """
    sopa = BeautifulSoup(html, "html.parser")
    mensagens: list[dict] = []
    for bloco in sopa.select(".tgme_widget_message"):
        texto = " ".join(
            (n.get_text(" ", strip=True) for n in bloco.select(".tgme_widget_message_text"))
        ).strip()
        if not texto:
            continue
        data = ""
        tag_data = bloco.select_one("time[datetime]")
        if tag_data:
            data = tag_data.get("datetime", "")
        link = bloco.select_one("a.tgme_widget_message_date")
        url = link.get("href", "") if link else ""
        vis = ""
        tag_vis = bloco.select_one(".tgme_widget_message_views")
        if tag_vis:
            vis = tag_vis.get_text(" ", strip=True)
        ident = bloco.get("data-post", "") or ""
        mensagens.append(
            {
                "id": ident,
                "texto": texto,
                "data": data,
                "visualizacoes": vis,
                "url": url,
            }
        )
        if len(mensagens) >= limite:
            break
    return mensagens


def _data_para_datetime(bruto: str) -> datetime | None:
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(bruto.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def coletar_canal(canal: str, limite: int = 20, timeout: float = 20.0) -> list[dict]:
    """Le as ultimas mensagens publicas de um canal.

    Devolve lista de dicts com `texto`, `data_publicacao`, `url`, `canal`.
    Falha silenciosa: devolve [] se o canal nao existir ou for privado.
    """
    try:
        resp = requests.get(
            url_publico(canal), timeout=timeout, headers={"User-Agent": USER_AGENT}
        )
        if resp.status_code != 200:
            return []
        mensagens = extrair_mensagens(resp.text, limite=limite)
    except Exception:  # noqa: BLE001
        return []

    saida: list[dict] = []
    for msg in mensagens:
        saida.append(
            {
                "id_externo": msg["id"] or f"tg-{hash(msg['url'] or msg['texto'])}",
                "plataforma": "Telegram",
                "tipo": "Postagem",
                "texto": msg["texto"],
                "data_publicacao": _data_para_datetime(msg["data"]),
                "url": msg["url"],
                "canal": canal.lstrip("@"),
                "visualizacoes": msg["visualizacoes"],
            }
        )
    return saida


RE_CANAL = re.compile(r"^[A-Za-z0-9_]{3,64}$")


def canal_valido(canal: str) -> bool:
    """Nome de canal publico do Telegram (sem link, sem '+invite')."""
    nome = (canal or "").strip().lstrip("@")
    if not nome or "+" in nome or "/" in nome:
        return False
    return bool(RE_CANAL.match(nome))
