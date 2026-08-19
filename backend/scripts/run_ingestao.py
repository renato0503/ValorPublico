import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger
from scraper.facebook_scraper import FacebookScraper
from scraper.instagram_scraper import InstagramScraper
from scraper.orchestrator import Orchestrator
from scraper.telegram_scraper import TelegramScraper
from scraper.twitter_scraper import TwitterScraper
from scraper.web_scraper import WebScraper
from scraper.youtube_scraper import YouTubeScraper

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
        scrapers.append(WebScraper(CONFIG_BASE))
    if settings.HABILITAR_YOUTUBE:
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
    if not scrapers:
        logger.warning("Nenhum scraper habilitado no .env.")
    return scrapers


async def main() -> None:
    db = init_firebase()
    orquestrador = Orchestrator(
        db,
        scrapers=construir_scrapers(),
        limite_por_agente=settings.LIMITE_ITENS_POR_AGENTE,
        max_workers=settings.MAX_WORKERS,
    )
    try:
        resumo = await orquestrador.executar()
        logger.info("Resumo final: %s", resumo)
    finally:
        orquestrador.fechar()


if __name__ == "__main__":
    asyncio.run(main())