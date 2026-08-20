import argparse
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger
from scraper.orchestrator import Orchestrator
from storage.firestore_repo import FirestoreRepo

logger = get_logger(__name__)

CONFIG_BASE = {
    "proxies": settings.PROXY_LIST,
    "delay_min": settings.SCRAPE_DELAY_MIN,
    "delay_max": settings.SCRAPE_DELAY_MAX,
    "incluir_comentarios": settings.INCLUIR_COMENTARIOS,
}


def construir_scrapers() -> list:
    scrapers: list = []
    if settings.HABILITAR_TWITTER:
        from scraper.twitter_scraper import TwitterScraper

        scrapers.append(
            TwitterScraper(
                {
                    **CONFIG_BASE,
                    "contas_twitter": settings.TWITTER_ACCOUNTS,
                    "cookies_file": settings.TWITTER_COOKIES_FILE,
                }
            )
        )
    if settings.HABILITAR_INSTAGRAM:
        from scraper.instagram_scraper import InstagramScraper

        scrapers.append(
            InstagramScraper(
                {
                    **CONFIG_BASE,
                    "username": settings.INSTAGRAM_USERNAME,
                    "password": settings.INSTAGRAM_PASSWORD,
                    "session_file": settings.INSTAGRAM_SESSION_FILE,
                    "max_posts_por_perfil": settings.INSTAGRAM_MAX_POSTS_PERFIL,
                }
            )
        )
    if settings.HABILITAR_FACEBOOK:
        from scraper.facebook_scraper import FacebookScraper

        scrapers.append(
            FacebookScraper(
                {
                    **CONFIG_BASE,
                    "cookies_file": settings.FACEBOOK_COOKIES_FILE,
                    "username": settings.FACEBOOK_USERNAME,
                    "password": settings.FACEBOOK_PASSWORD,
                    "headless": settings.FACEBOOK_HEADLESS,
                    "max_rolagens": settings.FACEBOOK_MAX_ROLAGENS,
                }
            )
        )
    if settings.HABILITAR_WEB:
        from scraper.web_scraper import WebScraper

        scrapers.append(
            WebScraper({**CONFIG_BASE, "enriquecer": settings.WEB_ENRIQUECER})
        )
    if settings.HABILITAR_YOUTUBE:
        from scraper.youtube_scraper import YouTubeScraper

        scrapers.append(
            YouTubeScraper(
                {
                    **CONFIG_BASE,
                    "coletar_transcricao": settings.YOUTUBE_COLETAR_TRANSCRICAO,
                    "max_videos": settings.YOUTUBE_MAX_VIDEOS,
                }
            )
        )
    if settings.HABILITAR_TELEGRAM:
        from scraper.telegram_scraper import TelegramScraper

        scrapers.append(
            TelegramScraper(
                {
                    **CONFIG_BASE,
                    "api_id": settings.TELEGRAM_API_ID,
                    "api_hash": settings.TELEGRAM_API_HASH,
                    "session_file": settings.TELEGRAM_SESSION_FILE,
                    "canais": settings.TELEGRAM_CANAIS,
                    "limite_por_canal": settings.TELEGRAM_LIMITE_POR_CANAL,
                }
            )
        )
    if settings.HABILITAR_TV:
        from scraper.tv_radio_scraper import TVScraper

        scrapers.append(
            TVScraper(
                {
                    **CONFIG_BASE,
                    "canais": settings.TV_CANAIS,
                    "max_videos_por_canal": settings.MIDIA_VIDEOS_POR_CANAL,
                }
            )
        )
    if settings.HABILITAR_RADIO:
        from scraper.tv_radio_scraper import RadioScraper

        scrapers.append(
            RadioScraper(
                {
                    **CONFIG_BASE,
                    "canais": settings.RADIO_CANAIS,
                    "max_videos_por_canal": settings.MIDIA_VIDEOS_POR_CANAL,
                }
            )
        )
    if settings.HABILITAR_IMPRESSO:
        from scraper.impresso_scraper import ImpressoScraper

        scrapers.append(ImpressoScraper({**CONFIG_BASE, "sites": settings.IMPRESSO_SITES}))
    if not scrapers:
        logger.warning("Nenhum scraper habilitado no .env.")
    return scrapers


async def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de ingestao do ValorPublico.")
    parser.add_argument(
        "--apenas-sem-dados",
        action="store_true",
        help="Processa apenas agentes que ainda nao possuem clippings (retomada).",
    )
    parser.add_argument(
        "--agentes",
        default="",
        help="Lista de IDs de agentes separados por virgula (ex.: samantha-iris,chico-2000).",
    )
    parser.add_argument(
        "--limite-agentes",
        type=int,
        default=None,
        help="Processa apenas os N primeiros agentes (apos os filtros).",
    )
    args = parser.parse_args()

    db = init_firebase()
    agente_ids: list[str] | None = None

    if args.agentes.strip():
        agente_ids = [a.strip() for a in args.agentes.split(",") if a.strip()]
    elif args.apenas_sem_dados:
        repo = FirestoreRepo(db)
        sem_dados = [
            a["id"] for a in repo.carregar_agentes() if not repo.tem_clippings(a["id"])
        ]
        if not sem_dados:
            logger.info("Nenhum agente sem clippings. Nada a fazer.")
            return
        agente_ids = sem_dados
        logger.info("Retomada: %d agentes sem clippings.", len(sem_dados))

    orquestrador = Orchestrator(
        db,
        scrapers=construir_scrapers(),
        limite_por_agente=settings.LIMITE_ITENS_POR_AGENTE,
        max_workers=settings.MAX_WORKERS,
        concorrencia_agentes=settings.PARALELISMO_AGENTES,
    )
    try:
        resumo = await orquestrador.executar(
            limite_agentes=args.limite_agentes,
            agente_ids=agente_ids,
        )
        logger.info("Resumo final: %s", resumo)
    finally:
        orquestrador.fechar()


if __name__ == "__main__":
    asyncio.run(main())