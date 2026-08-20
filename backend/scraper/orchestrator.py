import asyncio
from concurrent.futures import ThreadPoolExecutor

from core.logger import get_logger
from processing.cleaner import padronizar_dataframe
from processing.sentiment import AnalisadorSentimento
from processing.valoracao import Valorador
from scraper.base import AsyncScraper, BaseScraper
from scraper.models import RawItem
from storage.firestore_repo import FirestoreRepo

logger = get_logger(__name__)


class Orchestrator:
    """Orquestra a coleta paralela, o pipeline de NLP e a persistencia."""

    def __init__(
        self,
        db,
        scrapers: list,
        analisador: AnalisadorSentimento | None = None,
        valorador: Valorador | None = None,
        limite_por_agente: int = 50,
        max_workers: int = 8,
    ) -> None:
        self.repo = FirestoreRepo(db)
        self.scrapers = scrapers
        self.analisador = analisador or AnalisadorSentimento()
        self.valorador = valorador or Valorador(db)
        self.limite_por_agente = limite_por_agente
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    async def executar(
        self,
        cidades: list[str] | None = None,
        limite_agentes: int | None = None,
        agente_ids: list[str] | None = None,
    ) -> dict:
        agentes = self.repo.carregar_agentes(cidades)
        if agente_ids:
            ids = set(agente_ids)
            agentes = [a for a in agentes if a["id"] in ids]
        if limite_agentes:
            agentes = agentes[:limite_agentes]
        logger.info("Ingestao iniciada: %d agentes, %d scrapers", len(agentes), len(self.scrapers))

        total_gravados = 0
        itens_acumulados: list[RawItem] = []
        for indice, agente in enumerate(agentes, start=1):
            itens = await self._coletar_agente(agente)
            itens_acumulados.extend(itens)

            if not itens:
                logger.info("(%d/%d) %s: sem itens.", indice, len(agentes), agente["id"])
                continue

            df = padronizar_dataframe(itens)
            self.analisador.aplicar_dataframe(df)
            self.valorador.aplicar_dataframe(df)
            gravados = self.repo.salvar_lote(df)
            total_gravados += gravados
            logger.info("(%d/%d) %s: %d clippings gravados.", indice, len(agentes), agente["id"], gravados)

        resumo = {
            "total_agentes": len(agentes),
            "total_brutos": len(itens_acumulados),
            "total_gravados": total_gravados,
            "por_plataforma": {},
            "por_sentimento": {},
            "valoracao_total": 0.0,
        }
        self.repo.registrar_ultimo_scrape(resumo)
        logger.info("Ingestao finalizada: %s", resumo)
        return resumo

    async def _coletar_agente(self, agente: dict) -> list[RawItem]:
        """Coleta todos os scrapers para UM agente (async + sync em paralelo)."""
        loop = asyncio.get_running_loop()
        async_tasks = []
        sync_futures = []

        for scraper in self.scrapers:
            if isinstance(scraper, AsyncScraper):
                async_tasks.append(
                    asyncio.create_task(
                        self._guard_async(scraper.coletar(agente, self.limite_por_agente), scraper, agente)
                    )
                )
            elif isinstance(scraper, BaseScraper):
                sync_futures.append(
                    loop.run_in_executor(
                        self._pool, self._guard_sync, scraper, agente, self.limite_por_agente
                    )
                )
            else:
                logger.error("Scraper desconhecido ignorado: %r", scraper)

        itens: list[RawItem] = []
        if async_tasks:
            for resultado in await asyncio.gather(*async_tasks):
                if resultado:
                    itens.extend(resultado)
        for futuro in sync_futures:
            try:
                resultado = await asyncio.wrap_future(futuro)
            except Exception as e:  # noqa: BLE001
                logger.error("Scraper sincrono falhou no agente %s: %s", agente["id"], e)
                continue
            if resultado:
                itens.extend(resultado)
        return itens

    async def _guard_async(self, coro, scraper, agente):
        try:
            return await coro
        except Exception as e:  # noqa: BLE001
            logger.error("Scraper %s falhou no agente %s: %s", scraper.plataforma, agente["id"], e)
            return []

    def _guard_sync(self, scraper: BaseScraper, agente: dict, limite: int) -> list[RawItem]:
        try:
            return scraper.coletar(agente, limite)
        except Exception as e:  # noqa: BLE001
            logger.error("Scraper %s falhou no agente %s: %s", scraper.plataforma, agente["id"], e)
            return []

    def fechar(self) -> None:
        self._pool.shutdown(wait=True)