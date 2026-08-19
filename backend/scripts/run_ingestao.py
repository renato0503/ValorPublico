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
from scraper.twitter_scraper import TwitterScraper
from scraper.web_scraper import WebScraper

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
            TwitterScraper({**CONFIG_BASE, "contas_twitter": settings.TWITTER_ACCOUNTS})
        )
    if settings.HABILITAR_INSTAGRAM:
        scrapers.append(
            InstagramScraper(
                {
                    **CONFIG_BASE,
                    "username": settings.INSTAGRAM_USERNAME,
                    "password": settings.INSTAGRAM_PASSWORD,
                    "session_file": settings.INSTAGRAM_SESSION_FILE,
                }
            )
        )
    if settings.HABILITAR_FACEBOOK:
        scrapers.append(
            FacebookScraper({**CONFIG_BASE, "cookies_file": settings.FACEBOOK_COOKIES_FILE})
        )
    if settings.HABILITAR_WEB:
        scrapers.append(WebScraper(CONFIG_BASE))
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