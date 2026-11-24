"""Fontes de tendencias (plano 07) — todas oficiais e gratuitas.

T1  RSS do Google Trends (BR e BR-MT): assuntos em alta + noticias ligadas.
T2  trendspy (endpoint nao oficial, com trava de ritmo e cache) — opcional.
T4  Wikimedia Pageviews (visitas ao artigo na Wikipédia).
T5  GDELT DOC 2.0 (volume de noticias por termo; 1 chamada a cada 5 s).
T6  YouTube em alta (Data API v3; exige chave gratuita).

Regra do dono: nada pago. Sem chave = funciona so com T1/T4/T5.

Cada modulo falha **silenciosamente** (devolve lista vazia e registra o
motivo) para nunca derrubar a ingestao diaria.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import requests

USER_AGENT = "CerraClipping/1.0 (projeto de transparencia institucional; contato via GitHub renato0503)"

# --------------------------------------------------------------------------
# T1 — RSS do Google Trends
# --------------------------------------------------------------------------
TRENDS_RSS_BR = "https://trends.google.com/trending/rss?geo=BR"
TRENDS_RSS_BR_MT = "https://trends.google.com/trending/rss?geo=BR-MT"


def _parse_rss_trends(xml: str) -> list[dict]:
    """Normaliza o RSS do Trends: termo, volume e noticias ligadas.

    Usa o parser XML direto (o `feedparser` nao expoe de forma estavel os
    campos `ht:*` do Google Trends).
    """
    from xml.etree import ElementTree

    raiz = ElementTree.fromstring(xml)
    ns = {"ht": "https://trends.google.com/trending/rss"}
    itens: list[dict] = []
    for item in raiz.iter("item"):
        termo = (item.findtext("title") or "").strip()
        if not termo:
            continue
        trafego = (item.findtext("ht:approx_traffic", default="", namespaces=ns) or "").strip()
        noticias = []
        for news in item.findall("ht:news_item", ns):
            noticias.append(
                {
                    "titulo": (news.findtext("ht:news_item_title", default="", namespaces=ns) or "").strip(),
                    "url": (news.findtext("ht:news_item_url", default="", namespaces=ns) or "").strip(),
                    "fonte": (news.findtext("ht:news_item_source", default="", namespaces=ns) or "").strip(),
                }
            )
        itens.append(
            {
                "termo": termo,
                "volume": trafego,
                "noticias": noticias[:5],
                "url_feed": item.findtext("link") or "",
            }
        )
    return itens


def em_alta(geo: str = "BR-MT", timeout: float = 20.0) -> tuple[list[dict], str | None]:
    """Assuntos em alta no dia. Devolve (itens, erro)."""
    url = TRENDS_RSS_BR_MT if geo.upper() == "BR-MT" else TRENDS_RSS_BR
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return _parse_rss_trends(resp.text), None
    except Exception as exc:  # noqa: BLE001
        return [], f"RSS do Google Trends indisponivel: {exc}"


def em_alta_multiplas_geos(
    geos: tuple[str, ...] = ("BR-MT", "BR"), timeout: float = 20.0
) -> dict[str, list[dict]]:
    """Busca varios geos (um RSS por geo) e devolve {geo: itens}."""
    saida: dict[str, list[dict]] = {}
    for geo in geos:
        itens, _ = em_alta(geo, timeout=timeout)
        saida[geo] = itens
        time.sleep(1.0)
    return saida


# --------------------------------------------------------------------------
# T4 — Wikimedia Pageviews
# --------------------------------------------------------------------------
WIKIMEDIA_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "pt.wikipedia/all-access/user/{artigo}/daily/{inicio}/{fim}"
)


def pageviews_wikipedia(
    artigo: str,
    dias: int = 30,
    hoje: datetime | None = None,
    timeout: float = 20.0,
) -> tuple[list[dict], str | None]:
    """Serie diaria de visitas ao artigo na Wikipédia em portugues.

    Devolve ([{"data", "views"}], erro).
    """
    hoje = hoje or datetime.now(timezone.utc)
    fim = hoje.date()
    inicio = fim - timedelta(days=dias)
    url = WIKIMEDIA_URL.format(
        artigo=artigo.replace(" ", "_"),
        inicio=inicio.strftime("%Y%m%d"),
        fim=fim.strftime("%Y%m%d"),
    )
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        dados = resp.json()
        itens = [
            {
                "data": datetime.utcfromtimestamp(int(item["timestamp"][:8])).date().isoformat(),
                "views": int(item.get("views") or 0),
            }
            for item in dados.get("items", [])
        ]
        return itens, None
    except Exception as exc:  # noqa: BLE001
        return [], f"Pageviews indisponiveis: {exc}"


# --------------------------------------------------------------------------
# T5 — GDELT DOC 2.0
# --------------------------------------------------------------------------
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
PAUSA_GDELT = 5.0  # a API pede 1 chamada a cada 5 s


def gdelt_volume(
    termo: str,
    timespan: str = "7d",
    idioma: str = "portuguese",
    timeout: float = 30.0,
) -> tuple[list[dict], str | None]:
    """Volume de noticias por dia para um termo (timelinevol).

    Devolve ([{"data", "volume"}], erro).
    """
    params = {
        "query": f'{termo} sourcelang:{idioma}',
        "mode": "timelinevol",
        "timespan": timespan,
        "format": "json",
    }
    try:
        resp = requests.get(GDELT_URL, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        dados = resp.json()
        itens = [
            {"data": str(item.get("day", "")), "volume": float(item.get("volume") or 0)}
            for item in dados.get("timeline", [])
        ]
        return itens, None
    except Exception as exc:  # noqa: BLE001
        return [], f"GDELT indisponivel: {exc}"
    finally:
        time.sleep(PAUSA_GDELT)


# --------------------------------------------------------------------------
# T6 — YouTube em alta (Data API v3, exige chave gratuita)
# --------------------------------------------------------------------------
YOUTUBE_API = "https://www.googleapis.com/youtube/v3/videos"


def youtube_em_alta(
    api_key: str,
    region_code: str = "BR",
    max_results: int = 10,
    timeout: float = 20.0,
) -> tuple[list[dict], str | None]:
    """Videos mais populares no Brasil. Devolve ([{titulo, canal, views, url}], erro)."""
    if not api_key:
        return [], "Sem YOUTUBE_API_KEY (chave gratuita do Data API v3)."
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": max(1, min(int(max_results), 50)),
        "key": api_key,
    }
    try:
        resp = requests.get(YOUTUBE_API, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        dados = resp.json()
        itens = []
        for item in dados.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            vid = item.get("id", "")
            itens.append(
                {
                    "titulo": snippet.get("title", ""),
                    "canal": snippet.get("channelTitle", ""),
                    "views": int(stats.get("viewCount") or 0),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                }
            )
        return itens, None
    except Exception as exc:  # noqa: BLE001
        return [], f"YouTube em alta indisponivel: {exc}"


# --------------------------------------------------------------------------
# T2 — trendspy (opcional, endpoint nao oficial: 429 frequente)
# --------------------------------------------------------------------------
def interesse_de_busca(
    termos: list[str],
    geo: str = "BR-MT",
    timeframe: str = "today 3-m",
    cache: dict | None = None,
    pausa: float = 12.0,
) -> tuple[dict[str, list[dict]], str | None]:
    """Serie de interesse de busca por termo (Google Trends via trendspy).

    Devolve ({termo: [{"data", "valor"}]}, erro). Falha silenciosa: se a
    biblioteca nao estiver instalada ou o endpoint responder 429, devolve
    vazio e o motivo (o app mostra "dados insuficientes").
    """
    if cache is None:
        cache = {}
    try:
        from trendspy import TrendSpy
    except ImportError:
        return {}, "trendspy nao instalado (opcional; use o RSS do Trends)."

    series: dict[str, list[dict]] = {}
    erro: str | None = None
    for termo in termos:
        if termo in cache:
            series[termo] = cache[termo]
            continue
        try:
            ts = TrendSpy(geo=geo, timeframe=timeframe)
            df = ts.interest_over_time()
            if df is None or df.empty:
                series[termo] = []
            else:
                pontos = [
                    {"data": str(idx)[:10], "valor": float(valor)}
                    for idx, valor in df[termo].items()
                ]
                series[termo] = pontos
                cache[termo] = pontos
        except Exception as exc:  # noqa: BLE001
            erro = f"trendspy falhou para {termo!r}: {exc}"
            series[termo] = []
        time.sleep(pausa)
    return series, erro


def pico_de_atencao(serie: list[dict], fator_limite: float = 3.0) -> dict:
    """Regra do pico (plano 07 §2): hoje > media de 28 dias x fator.

    Devolve {"ativo": bool, "fator": float, "base_dias": int}.
    """
    pontos = [p for p in (serie or []) if p.get("valor") is not None]
    if len(pontos) < 8:
        return {"ativo": False, "fator": 0.0, "base_dias": len(pontos)}
    pontos = sorted(pontos, key=lambda p: p["data"])
    base = pontos[-29:-1] or pontos[:-1]
    media = sum(float(p["valor"]) for p in base) / len(base) if base else 0.0
    hoje = float(pontos[-1]["valor"])
    fator = (hoje / media) if media > 0 else (0.0 if hoje == 0 else 999.0)
    return {
        "ativo": bool(media > 0 and fator >= fator_limite),
        "fator": round(fator, 2),
        "base_dias": len(base),
    }
