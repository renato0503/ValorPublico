from datetime import datetime, timezone

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import TIPO_NOTICIA, PLATAFORMA_WEB, RawItem

logger = get_logger(__name__)


class WebScraper(BaseScraper):
    """Monitora midia tradicional (portais de noticia) via RSS do Google News.

    O texto das paginas e extraido com o Trafilatura (referencia F1 em 2026),
    que remove boilerplate e produz texto limpo pronto para NLP/RAG. A rede e
    adquirida via httpx (HTTP/2), com o corpo repassado ao feedparser.
    """

    plataforma = PLATAFORMA_WEB

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.enriquecer = cfg.get("enriquecer", True)

    def _buscar_rss(self, termo: str, limite: int) -> list[dict]:
        import feedparser

        url = "https://news.google.com/rss/search"
        resp = self._get(
            url,
            params={"q": termo, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
        )
        feed = feedparser.parse(resp.content)
        return feed.entries[:limite]

    def _extrair_texto(self, url: str) -> str:
        """Corpo do artigo limpo via Trafilatura (fallback: marcacao markdown)."""
        try:
            import trafilatura

            resp = self._get(url)
            texto = trafilatura.extract(
                resp.text,
                include_comments=False,
                include_tables=False,
                favor_recall=True,
            )
            if not texto:
                texto = trafilatura.extract(
                    resp.text,
                    output_format="markdown",
                    include_comments=False,
                    favor_recall=True,
                )
            return (texto or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.debug("Web: nao foi possivel enriquecer %s: %s", url, e)
            return ""

    def _data_publicacao(self, entrada: dict) -> datetime | None:
        if entrada.get("published_parsed"):
            return datetime(*entrada["published_parsed"][:6], tzinfo=timezone.utc)
        return None

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        itens: list[RawItem] = []
        for termo in agente.get("termos_de_busca", []):
            try:
                for entrada in self._buscar_rss(termo, limite):
                    titulo = entrada.get("title", "")
                    resumo = entrada.get("summary", "")
                    veiculo = entrada.get("source", {}).get("title", "")
                    url = entrada.get("link", "")
                    texto = f"{titulo} {resumo}"
                    if self.enriquecer:
                        corpo = self._extrair_texto(url)
                        if corpo:
                            texto = f"{titulo} {corpo}"
                    itens.append(
                        RawItem(
                            agente_id=agente["id"],
                            id_externo=self._hash_id(url),
                            plataforma=self.plataforma,
                            tipo=TIPO_NOTICIA,
                            texto_limpo=texto,
                            data_publicacao=self._data_publicacao(entrada),
                            autor=veiculo,
                            url=url,
                            alcance=0,
                            metadados={"veiculo": veiculo},
                        )
                    )
                self._sleep()
            except Exception as e:  # noqa: BLE001
                logger.warning("Web: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("Web: %d itens para %s", len(itens), agente["id"])
        return itens