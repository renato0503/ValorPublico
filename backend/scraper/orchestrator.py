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
    ) -> dict:
        agentes = self.repo.carregar_agentes(cidades)
        if limite_agentes:
            agentes = agentes[:limite_agentes]
        logger.info("Ingestao iniciada: %d agentes, %d scrapers", len(agentes), len(self.scrapers))

        async_tasks: list[asyncio.Task] = []
        sync_futures = []
        loop = asyncio.get_running_loop()

        for scraper in self.scrapers:
            if isinstance(scraper, AsyncScraper):
                async_tasks.append(asyncio.create_task(self._coletar_async(scraper, agentes)))
            elif isinstance(scraper, BaseScraper):
                sync_futures.append(
                    loop.run_in_executor(self._pool, self._coletar_sync, scraper, agentes)
                )
            else:
                logger.error("Scraper desconhecido ignorado: %r", scraper)

        resultados: list = []
        if async_tasks:
            resultados += await asyncio.gather(*async_tasks, return_exceptions=True)
        for futuro in sync_futures:
            try:
                resultados.append(await asyncio.wrap_future(futuro))
            except Exception as e:  # noqa: BLE001
                logger.error("Scraper sincrono falhou: %s", e)

        itens: list[RawItem] = []
        for r in resultados:
            if isinstance(r, Exception):
                logger.error("Erro em execucao de scraper: %s", r)
            elif r:
                itens.extend(r)

        logger.info("Coleta concluida: %d itens brutos.", len(itens))
        df = padronizar_dataframe(itens)
        self.analisador.aplicar_dataframe(df)
        self.valorador.aplicar_dataframe(df)
        total_gravados = self.repo.salvar_lote(df)

        resumo = {
            "total_agentes": len(agentes),
            "total_brutos": len(itens),
            "total_gravados": total_gravados,
            "por_plataforma": df["plataforma"].value_counts().to_dict() if not df.empty else {},
            "por_sentimento": df["sentimento"].value_counts().to_dict() if not df.empty else {},
            "valoracao_total": round(float(df["valor_estimado"].sum()), 2) if not df.empty else 0.0,
        }
        self.repo.registrar_ultimo_scrape(resumo)
        logger.info("Ingestao finalizada: %s", resumo)
        return resumo

    async def _coletar_async(self, scraper: AsyncScraper, agentes: list[dict]) -> list[RawItem]:
        tarefas = [scraper.coletar(agente, self.limite_por_agente) for agente in agentes]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        itens: list[RawItem] = []
        for agente, r in zip(agentes, resultados):
            if isinstance(r, Exception):
                logger.error("Scraper %s falhou no agente %s: %s", scraper.plataforma, agente["id"], r)
            else:
                itens.extend(r)
        return itens

    def _coletar_sync(self, scraper: BaseScraper, agentes: list[dict]) -> list[RawItem]:
        itens: list[RawItem] = []
        for agente in agentes:
            try:
                itens.extend(scraper.coletar(agente, self.limite_por_agente))
            except Exception as e:  # noqa: BLE001
                logger.error("Scraper %s falhou no agente %s: %s", scraper.plataforma, agente["id"], e)
        return itens

    def fechar(self) -> None:
        self._pool.shutdown(wait=True)