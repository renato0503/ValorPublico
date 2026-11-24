"""Testa o SearXNG do container (motor n1 da busca social).

Roda no CI antes da coleta: se o container nao responder em JSON, o job
avisa logo (em vez de coletar zero item silenciosamente).

Uso (a partir de `backend/`):
    python scripts/testar_searxng.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.scraper.searxng_cliente import SearXNGCliente, SearXNGIndisponivel
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

CONSULTA = '"Cuiabá" (site:instagram.com OR site:facebook.com)'


def main() -> int:
    if not settings.SEARXNG_URL:
        logger.warning("SEARXNG_URL nao configurada: a busca social usara o ddgs.")
        return 0

    cliente = SearXNGCliente(url_base=settings.SEARXNG_URL, motores=settings.SEARXNG_MOTORES)
    try:
        resultados = cliente.buscar(CONSULTA, 3)
    except SearXNGIndisponivel as exc:
        logger.error("SearXNG indisponivel: %s", exc)
        return 1

    if not resultados:
        logger.error("SearXNG respondeu sem resultados para a consulta de teste.")
        return 1

    logger.info("SearXNG OK: %d resultados.", len(resultados))
    for item in resultados[:3]:
        logger.info("  - %s | %s", (item.get("titulo") or "")[:70], item.get("url", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
