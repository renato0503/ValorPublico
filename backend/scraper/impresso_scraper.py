from datetime import datetime, timezone

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import TIPO_NOTICIA, PLATAFORMA_IMPRESSO, RawItem

logger = get_logger(__name__)


class ImpressoScraper(BaseScraper):
    """Captura materias de jornais impressos com edicao digital.

    Para cada site configurado tenta o RSS (mais barato); sem RSS, extrai o
    texto da homepage com Trafilatura. Em ambos os casos filtra materias que
    mencionam os termos de busca do agente (nome + cargo + partido).
    """

    plataforma = PLATAFORMA_IMPRESSO

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.sites: list[str] = cfg.get("sites", [])

    def _data_publicacao(self, entrada: dict) -> datetime | None:
        if entrada.get("published_parsed"):
            return datetime(*entrada["published_parsed"][:6], tzinfo=timezone.utc)
        return None

    def _menciona(self, texto: str, termos: list[str]) -> bool:
        t = texto.lower()
        return any(termo.lower() in t for termo in termos)

    def _coletar_rss(self, site: str, termos: list[str], limite: int) -> list[RawItem]:
        import feedparser

        itens: list[RawItem] = []
        for sufixo in ("/feed", "/rss", "/rss.xml", "/feed.xml"):
            url = f"{site}{sufixo}"
            try:
                resp = self._get(url)
                feed = feedparser.parse(resp.content)
                if not feed.entries:
                    continue
                for entrada in feed.entries[:limite]:
                    titulo = entrada.get("title", "")
                    resumo = entrada.get("summary", "")
                    if not self._menciona(f"{titulo} {resumo}", termos):
                        continue
                    link = entrada.get("link", "")
                    itens.append(
                        RawItem(
                            agente_id="",  # preenchido no coletar
                            id_externo=self._hash_id(link),
                            plataforma=self.plataforma,
                            tipo=TIPO_NOTICIA,
                            texto_limpo=f"{titulo} {resumo}".strip(),
                            data_publicacao=self._data_publicacao(entrada),
                            autor=site,
                            url=link,
                            alcance=0,
                            metadados={"veiculo": site, "origem": "rss"},
                        )
                    )
                self._sleep()
                return itens
            except Exception as e:  # noqa: BLE001
                logger.debug("Impresso: RSS indisponivel em %s%s: %s", site, sufixo, e)
        return itens

    def _coletar_homepage(self, site: str, termos: list[str]) -> list[RawItem]:
        import trafilatura

        try:
            resp = self._get(site)
            texto = trafilatura.extract(resp.text, include_comments=False) or ""
            if not self._menciona(texto, termos):
                return []
            return [
                RawItem(
                    agente_id="",  # preenchido no coletar
                    id_externo=self._hash_id(site),
                    plataforma=self.plataforma,
                    tipo=TIPO_NOTICIA,
                    texto_limpo=texto[:4000],
                    data_publicacao=None,
                    autor=site,
                    url=site,
                    alcance=0,
                    metadados={"veiculo": site, "origem": "homepage"},
                )
            ]
        except Exception as e:  # noqa: BLE001
            logger.warning("Impresso: falha na homepage %s: %s", site, e)
            return []

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        itens: list[RawItem] = []
        if not self.sites:
            logger.warning("Impresso: nenhum site configurado (IMPRESSO_SITES).")
            return itens
        termos = agente.get("termos_de_busca", [])

        for site in self.sites:
            itens_site = self._coletar_rss(site, termos, limite) or self._coletar_homepage(site, termos)
            for item in itens_site:
                item.agente_id = agente["id"]
            itens.extend(itens_site)

        logger.info("Impresso: %d itens para %s", len(itens), agente["id"])
        return itens