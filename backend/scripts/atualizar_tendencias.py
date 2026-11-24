"""Atualiza os agregados de tendencias, crise e previsao (E1 do plano 15).

Grava (com `merge=True`, so agregados < 1 MiB):
  metricas/geral              -> .tendencias  .crise  .previsao  .anuncios_politicos
  metricas_por_cidade/<slug>  -> .tendencias  .crise
  metricas_por_agente/<id>     -> .tendencias  .crise

Fontes (todas oficiais e gratuitas, plano 07):
  - RSS do Google Trends (BR e BR-MT)
  - Wikimedia Pageviews (artigo do agente)
  - GDELT DOC 2.0 (volume por termo)
  - YouTube em alta (Data API v3, se houver chave)
  - Meta Ad Library (se houver token)

Uso (a partir de `backend/`):
    python scripts/atualizar_tendencias.py
    python scripts/atualizar_tendencias.py --sem-firestore   # so coleta e imprime
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.processing.indicadores import (
    agrupar_por_dia,
    indice_crise,
    projetar,
    resumo_projeccao,
)
from cerra_nucleo.scraper.ad_library import agregar_por_estado
from cerra_nucleo.scraper.ad_library import consultar as consultar_ad_library
from cerra_nucleo.scraper.tendencias import (
    em_alta_multiplas_geos,
    gdelt_volume,
    pageviews_wikipedia,
    pico_de_atencao,
    youtube_em_alta,
)
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def coletar_tendencias_gerais() -> dict:
    """RSS do Trends (BR e BR-MT) + YouTube em alta + GDELT do termo 'Cuiaba'."""
    saida: dict = {"em_alta_mt": [], "em_alta_br": [], "youtube_em_alta_br": [], "gdelt": {}}

    geos = em_alta_multiplas_geos(("BR-MT", "BR"))
    saida["em_alta_mt"] = geos.get("BR-MT", [])[: settings.TENDENCIAS_MAX_ITENS]
    saida["em_alta_br"] = geos.get("BR", [])[: settings.TENDENCIAS_MAX_ITENS]

    if settings.YOUTUBE_API_KEY:
        itens, erro = youtube_em_alta(settings.YOUTUBE_API_KEY, max_results=10)
        if erro:
            logger.warning("YouTube em alta: %s", erro)
        saida["youtube_em_alta_br"] = itens[:10]

    serie, erro = gdelt_volume("Cuiaba", timespan="7d")
    if erro:
        logger.warning("GDELT: %s", erro)
    else:
        saida["gdelt"] = {"termo": "Cuiaba", "serie": serie}

    saida["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    return saida


def coletar_tendencias_agente(agente: dict) -> dict:
    """Interesse de busca + pageviews + pico para um agente."""
    saida: dict = {"atualizado_em": datetime.now(timezone.utc).isoformat()}
    nome = (agente.get("nome_urna") or "").strip()
    artigo = (agente.get("wikipedia_artigo") or "").strip()

    serie: list[dict] = []
    if artigo:
        pontos, erro = pageviews_wikipedia(artigo, dias=30)
        if erro:
            logger.info("Wikipedia (%s): %s", artigo, erro)
        else:
            serie = pontos

    saida["wikipedia"] = {
        "artigo": artigo,
        "views_30d": sum(p["views"] for p in serie),
        "serie": serie[-30:],
    }
    saida["pico"] = pico_de_atencao(serie) if serie else {"ativo": False, "fator": 0.0}
    saida["interesse_busca"] = {
        "geo": settings.TENDENCIAS_GEO,
        "ancora": nome,
        "fonte": "wikipedia_pageviews" if serie else "indisponivel",
        "serie": serie[-90:],
    }
    return saida


def serie_negativos(clippings: list[dict]) -> dict[str, int]:
    """Conta os negativos por dia (base do K-28)."""
    contagem: dict[str, int] = {}
    for item in clippings or []:
        if str(item.get("sentimento", "")).lower() != "negativo":
            continue
        chave = str(item.get("data_publicacao") or "")[:10]
        if not chave:
            continue
        contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza tendencias, crise e previsao.")
    parser.add_argument("--sem-firestore", action="store_true", help="so coleta (dry-run)")
    args = parser.parse_args()

    logger.info("Coletando tendencias...")
    gerais = coletar_tendencias_gerais()
    logger.info(
        "Tendencias: %d em alta em MT, %d em alta no BR, %d videos em alta.",
        len(gerais["em_alta_mt"]), len(gerais["em_alta_br"]), len(gerais["youtube_em_alta_br"]),
    )

    anuncios: list[dict] = []
    if settings.META_AD_LIBRARY_TOKEN:
        anuncios, erro = consultar_ad_library(settings.META_AD_LIBRARY_TOKEN, limite=50)
        if erro:
            logger.warning("Ad Library: %s", erro)
        else:
            logger.info("Ad Library: %d anuncios alcancando MT.", len(anuncios))

    if args.sem_firestore:
        print("Dry-run: tendencias coletadas (detalhes no log).")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()

    # Clippings para a crise e a previsao (L1 ja traz o sentimento).
    clippings: list[dict] = []
    for doc in db.collection("agentes_publicos").stream():
        for clip in doc.reference.collection("clippings").stream():
            clippings.append(clip.to_dict())
    logger.info("Lidos %d clippings para o calculo de crise e previsao.", len(clippings))

    hora = datetime.now(timezone.utc)
    crise = indice_crise(serie_negativos(clippings), agora=hora)
    previsao = projetar(agrupar_por_dia(clippings))
    logger.info("Crise: ativo=%s z=%s | Previsao: %s", crise["ativo"], crise["z"], previsao.get("metodo"))

    patch_geral: dict = {
        "tendencias": gerais,
        "crise": crise,
        "previsao": {
            "mencoes": previsao,
            "resumo": resumo_projeccao(previsao),
            "atualizado_em": hora.isoformat(),
        },
    }
    if anuncios:
        patch_geral["anuncios_politicos"] = agregar_por_estado(anuncios, "MT")

    db.collection("metricas").document("geral").set(patch_geral, merge=True)
    logger.info("metricas/geral: tendencias, crise e previsao gravadas.")

    # Por cidade (usa o mesmo doc que o front ja le).
    cidades = sorted({str(c.get("cidade") or "sem cidade") for c in clippings})
    from scripts.atualizar_metricas import slugify_cidade

    for cidade in cidades:
        db.collection("metricas_por_cidade").document(slugify_cidade(cidade)).set(
            {"tendencias": gerais, "crise": crise}, merge=True
        )
    logger.info("metricas_por_cidade: %d documentos atualizados.", len(cidades))

    # Por agente: interesse de busca + pico (wikipedia/trends).
    total = 0
    for doc in db.collection("agentes_publicos").stream():
        dados = doc.to_dict() or {}
        item = coletar_tendencias_agente({**dados, "id": doc.id})
        db.collection("metricas_por_agente").document(doc.id).set(
            {"tendencias": item, "crise": crise}, merge=True
        )
        total += 1
    logger.info("metricas_por_agente: %d documentos atualizados.", total)
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "atualizar_tendencias"))
