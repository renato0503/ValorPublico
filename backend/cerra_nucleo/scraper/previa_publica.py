"""Previa publica de link de rede social (N2 do plano 19).

Abre a URL encontrada pelo buscador **sem login** e le as meta tags publicas
(`og:title`, `og:description`, `og:image`, `og:url`, data de publicacao). E o
mesmo que o preview de link do WhatsApp: nao autenticamos, nao默认为 seguir.

Se a rede pedir login ou bloquear, o coletor PARA (19 §3.1.2) e devolve o que
tinha (title/snippet do buscador).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.scraper.navegador import BloqueioDetectado, SessaoNavegador

logger = get_logger(__name__)

# Redes onde a previa publica costuma funcionar.
REDES_COM_PREVIA = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "tiktok.com": "TikTok",
    "x.com": "Twitter",
    "twitter.com": "Twitter",
    "threads.net": "Threads",
    "kwai.com": "Kwai",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
}

RE_DATA = re.compile(
    r"(?:property|content)=\"(article:published_time|og:updated_time)\"",
)


@dataclass
class Previa:
    """Meta tags publicas de um link."""

    url: str
    ok: bool = False
    titulo: str = ""
    descricao: str = ""
    imagem: str = ""
    site: str = ""
    tipo: str = ""
    publicado_em: str = ""
    plataforma: str = ""
    motivo: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _meta(html: str, chave: str) -> str:
    """Le uma meta tag (property/name) do HTML."""
    padroes = (
        rf'<meta[^>]+property="{re.escape(chave)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="{re.escape(chave)}"',
        rf'<meta[^>]+name="{re.escape(chave)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+name="{re.escape(chave)}"',
    )
    for padrao in padroes:
        achado = re.search(padrao, html, re.IGNORECASE)
        if achado:
            return achado.group(1).strip()
    return ""


def extrair_meta(html: str) -> dict:
    """Extrai as meta tags publicas do HTML (funcao pura, facil de testar)."""
    titulo = _meta(html, "og:title") or _meta(html, "twitter:title")
    if not titulo:
        achado = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        titulo = (achado.group(1).strip() if achado else "")
    return {
        "titulo": titulo,
        "descricao": _meta(html, "og:description")
        or _meta(html, "twitter:description")
        or _meta(html, "description"),
        "imagem": _meta(html, "og:image") or _meta(html, "twitter:image"),
        "site": _meta(html, "og:site_name"),
        "tipo": _meta(html, "og:type"),
        "publicado_em": _meta(html, "article:published_time"),
    }


def plataforma_do_link(url: str) -> str:
    """Plataforma a partir do dominio do link."""
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for dominio, plataforma in REDES_COM_PREVIA.items():
        if host == dominio or host.endswith("." + dominio):
            return plataforma
    return ""


def previa_de(url: str, sessao: SessaoNavegador, agente_id: str | None = None) -> Previa:
    """Abre o link e devolve as meta tags publicas.

    Nunca levanta excecao para o chamador: devolve `Previa(ok=False, motivo=...)`.
    """
    saida = Previa(url=url, plataforma=plataforma_do_link(url))
    try:
        page = sessao.abrir_pagina(url, agente_id=agente_id)
    except BloqueioDetectado as exc:
        saida.motivo = f"bloqueio:{exc.tipo}"
        return saida
    except Exception as exc:  # noqa: BLE001
        saida.motivo = f"erro:{str(exc)[:120]}"
        return saida
    try:
        html = page.content()
        meta = extrair_meta(html)
        saida.ok = bool(meta["titulo"] or meta["descricao"] or meta["imagem"])
        saida.titulo = meta["titulo"]
        saida.descricao = meta["descricao"]
        saida.imagem = meta["imagem"]
        saida.site = meta["site"]
        saida.tipo = meta["tipo"]
        saida.publicado_em = meta["publicado_em"]
        if not saida.ok:
            saida.motivo = "sem_meta_tags"
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001
            pass
    return saida
