"""Coletor de redes sociais **publicas** via navegador (N8/N9 do plano 19).

Substitui o antigo `facebook_scraper.py` (que usava cookies de sessao e
login): aqui nao ha cookie de terceiro nem login de conta alheia. O coletor:

  - abre a **pagina publica** do perfil/post no navegador (Chromium ou, com a
    flag `NAVEGADOR_STEALTH`, Patchright/Camoufox);
  - le o que a pagina publica mostra (nome, legenda, data, curtidas,
    comentarios visiveis, imagem);
  - **para** ao encontrar login ou CAPTCHA (19 §3.1.2), registrando o bloqueio
    e nao tentando de novo por 24 h;
  - respeita o ritmo (<= 1 pagina a cada 5–10 s por dominio) e o limite diario
    por agente (<= 30 paginas).

Liberado pelo dono (24/11/2026): tambem pode usar a **conta logada do proprio
agente** (flag `NAVEGADOR_CONTA_PROPRIA`), reaproveitando o perfil do
navegador do dono — sem senha no repositorio.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.scraper.navegador import BloqueioDetectado, SessaoNavegador

logger = get_logger(__name__)

PLATAFORMA = "Redes"

# URLs publicas por rede (sem login).
PADROES_URL = {
    "instagram.com": ("Instagram", r"^https?://(www\.)?instagram\.com/(p|reel|tv)/[A-Za-z0-9_\-]+"),
    "facebook.com": ("Facebook", r"^https?://(www\.)?facebook\.com/[A-Za-z0-9\-.]+/posts/\d+"),
    "tiktok.com": ("TikTok", r"^https?://(www\.)?tiktok\.com/@[A-Za-z0-9_\-.]+/video/\d+"),
    "x.com": ("Twitter", r"^https?://(www\.)?x\.com/[A-Za-z0-9_]+/status/\d+"),
    "twitter.com": ("Twitter", r"^https?://(www\.)?twitter\.com/[A-Za-z0-9_]+/status/\d+"),
    "threads.net": ("Threads", r"^https?://(www\.)?threads\.net/@[A-Za-z0-9_\-.]+"),
}

RE_METADADOS = {
    "titulo": re.compile(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', re.IGNORECASE),
    "descricao": re.compile(
        r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', re.IGNORECASE
    ),
    "imagem": re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', re.IGNORECASE),
    "data": re.compile(
        r'<meta[^>]+property="article:published_time"[^>]+content="([^"]*)"', re.IGNORECASE
    ),
}


def plataforma_e_padrao(url: str) -> tuple[str, str | None]:
    """Devolve (plataforma, padrao de URL) para um link de rede."""
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for dominio, (plataforma, padrao) in PADROES_URL.items():
        if host == dominio or host.endswith("." + dominio):
            return plataforma, padrao
    return "", None


def extrair_publico(html: str) -> dict:
    """Le os dados publicos de um post (funcao pura, facil de testar)."""
    saida = {"titulo": "", "descricao": "", "imagem": "", "data": ""}
    for chave, padrao in RE_METADADOS.items():
        achado = padrao.search(html or "")
        if achado:
            saida[chave] = achado.group(1).strip()
    if not saida["titulo"]:
        achado = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.IGNORECASE | re.DOTALL)
        saida["titulo"] = (achado.group(1).strip() if achado else "")
    return saida


def coletar_link(
    url: str,
    sessao: SessaoNavegador,
    agente_id: str,
    conta_propria: bool = False,
) -> dict | None:
    """Abre um link publico e devolve um `RawItem`-ready dict (ou None).

    Nunca levanta excecao: devolve None quando a rede pede login/CAPTCHA.
    """
    plataforma, padrao = plataforma_e_padrao(url)
    if not plataforma or not padrao or not re.match(padrao, url):
        return None
    try:
        page = sessao.abrir_pagina(url, agente_id=agente_id)
    except BloqueioDetectado as exc:
        logger.info("Link %s bloqueado (%s); seguindo com o snippet.", url, exc.tipo)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.info("Falha ao abrir %s: %s", url, str(exc)[:100])
        return None
    try:
        html = page.content()
        meta = extrair_publico(html)
        if not meta["titulo"] and not meta["descricao"]:
            return None
        texto = " — ".join(p for p in (meta["titulo"], meta["descricao"]) if p).strip()
        return {
            "plataforma": plataforma,
            "titulo": meta["titulo"],
            "descricao": meta["descricao"],
            "imagem": meta["imagem"],
            "texto": texto,
            "url": url,
            "data": meta["data"],
            "conta_propria": conta_propria,
            "origem_coleta": "navegador",
        }
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001
            pass


def _data_para_datetime(bruto: str) -> datetime | None:
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(bruto.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
