import random
import time
from abc import ABC, abstractmethod

import requests

from core.logger import get_logger
from scraper.models import RawItem

logger = get_logger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class ResilienciaMixin:
    """Delays randomicos, rotacao de proxies e retry com backoff exponencial."""

    def __init__(
        self,
        proxies: list[str] | None = None,
        delay_min: float = 2.0,
        delay_max: float = 6.0,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> None:
        self.proxies = list(proxies or [])
        self._proxy_idx = 0
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _proximo_proxy(self) -> str | None:
        if not self.proxies:
            return None
        proxy = self.proxies[self._proxy_idx % len(self.proxies)]
        self._proxy_idx += 1
        return proxy

    def com_resiliencia(self, fn, *args, **kwargs):
        """Executa `fn` com retry + backoff exponencial + delay entre tentativas."""
        ultimo_erro: Exception | None = None
        for tentativa in range(1, self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                ultimo_erro = e
                logger.warning(
                    "Falha (tentativa %d/%d): %s", tentativa, self.max_retries, e
                )
                self._sleep()
                time.sleep(self.backoff_base**tentativa)
        raise ultimo_erro

    def _cabecalhos(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }


class BaseScraper(ResilienciaMixin, ABC):
    """Scraper sincrono (Instagram, Facebook, Web) com client HTTP resiliente."""

    plataforma: str = "Web"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        super().__init__(
            proxies=cfg.get("proxies"),
            delay_min=cfg.get("delay_min", 2.0),
            delay_max=cfg.get("delay_max", 6.0),
            max_retries=cfg.get("max_retries", 3),
        )
        self.incluir_comentarios = cfg.get("incluir_comentarios", True)
        self.session = requests.Session()

    def _get(self, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers.update(self._cabecalhos())
        params = kwargs.pop("params", None)

        def _fetch() -> requests.Response:
            proxies = None
            proxy = self._proximo_proxy()
            if proxy:
                proxies = {"http": proxy, "https": proxy}
            return self.session.get(
                url, headers=headers, params=params, proxies=proxies, timeout=30, **kwargs
            )

        resp = self.com_resiliencia(_fetch)
        resp.raise_for_status()
        return resp

    def _hash_id(self, texto: str) -> str:
        import hashlib

        return hashlib.md5(texto.encode("utf-8")).hexdigest()

    @abstractmethod
    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        """Coleta postagens/comentarios de um agente e retorna RawItems."""


class AsyncScraper(ResilienciaMixin, ABC):
    """Scraper assincrono (Twitter/twscrape)."""

    plataforma: str = "Twitter"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        super().__init__(
            proxies=cfg.get("proxies"),
            delay_min=cfg.get("delay_min", 2.0),
            delay_max=cfg.get("delay_max", 6.0),
            max_retries=cfg.get("max_retries", 3),
        )
        self.incluir_comentarios = cfg.get("incluir_comentarios", True)

    async def _sleep_async(self) -> None:
        import asyncio

        await asyncio.sleep(random.uniform(self.delay_min, self.delay_max))

    @abstractmethod
    async def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        """Coleta postagens/comentarios de um agente e retorna RawItems."""