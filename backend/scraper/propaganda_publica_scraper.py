"""Scraper do radar de propaganda publica / institucional.

Coleta as publicacoes oficiais (propaganda institucional, publicidade de
utilidade publica, diarios oficiais, portarias, licitacoes) nas fontes
configuradas em `FONTES_PROPAGANDA_PUBLICA`. Cada item nasce marcado com
`classe = propaganda_publica`, o que alimenta o radar (transparencia e
prova) e as regras de compliance (uso de simbolos publicos, art. 40).

Extracao em quatro camadas (a primeira que devolver itens vence):
  1. RSS/Atom  (feedparser) - ex.: Prefeitura de Varzea Grande (/feed)
  2. Texto principal (trafilatura) - ex.: Prefeitura de Cuiaba (/noticias)
  3. Titulos (h1..h5) - ex.: Secom-MT, Camara Municipal de Cuiaba
  4. Links de conteudo com texto - ex.: DOE-MT (IOnews), iomat, VG

As fontes sao paginas/feeds publicos de orgaos (prefeituras, casas de lei,
diarios oficiais, portais de transparencia). Nada autenticado e coletado.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from core.logger import get_logger
from processing.propaganda_publica import classificar_orgao, orgao_por_dominio
from scraper.base import BaseScraper
from scraper.models import PLATAFORMA_WEB, TIPO_NOTICIA, RawItem

logger = get_logger(__name__)

# Paginas acima deste tamanho sao ignoradas pelo radar (use o feed oficial)
TAMANHO_MAX_PAGINA = 8_000_000

# Padroes de link que indicate conteudo publicavel
_RE_LINK_CONTEUDO = re.compile(
    r"(/noticias/|/noticia/|/conteudo/|/publicacacoes/|/publicacoes_ver_conteudo/|"
    r"/visualizar/|/clipping/|/edicoes/)",
    re.IGNORECASE,
)
_RE_TITULO = re.compile(r"<h[1-5][^>]*>(.*?)</h[1-5]>", re.IGNORECASE | re.DOTALL)
_RE_ANCHOR = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_RE_TAG = re.compile(r"<[^>]+>")
# Paginas de erro / WAF / bloqueios
_RE_ERRO = re.compile(
    r"(the requested url was rejected|access denied|forbidden|erro\s*\d{3}|"
    r"p[áa]gina n[ãa]o encontrada|acesso negado|servidor indispon[íi]vel)",
    re.IGNORECASE,
)
# Titulos que sao apenas datas ("Quinta-feira, 19 de Novembro de 2026")
_RE_SO_DATA = re.compile(
    r"^\W*(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)[-\s].{0,80}"
    r"(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|"
    r"novembro|dezembro)(.{0,12})$",
    re.IGNORECASE,
)


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", _RE_TAG.sub(" ", texto or "")).strip()


class PropagandaPublicaScraper(BaseScraper):
    """Coleta publicacoes oficiais para o radar de propaganda publica."""

    plataforma = PLATAFORMA_WEB

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        super().__init__(cfg)
        self.fontes: list[str] = list(cfg.get("fontes") or [])
        self.max_itens: int = int(cfg.get("max_itens") or 20)

    # ------------------------------------------------------------------
    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        itens: list[RawItem] = []
        if not self.fontes:
            return itens
        alvo = min(limite, self.max_itens, 50)
        for fonte in self.fontes:
            if len(itens) >= alvo:
                break
            try:
                itens.extend(self._coletar_fonte(fonte, len(itens), alvo))
            except Exception as e:  # noqa: BLE001
                logger.error("Falha no radar de propaganda publica (%s): %s", fonte, e)
        return itens[:alvo]

    # ------------------------------------------------------------------
    def _coletar_fonte(self, url: str, ja_coletados: int, alvo: int) -> list[RawItem]:
        resposta = self._get(url)
        # Paginas muito pesadas (listas com milhares de itens) sao ignoradas:
        # a mesma informacao vem pelo feed oficial, com menos custo.
        try:
            peso = int(resposta.headers.get("content-length") or 0)
        except (TypeError, ValueError):
            peso = 0
        if peso > TAMANHO_MAX_PAGINA:
            logger.warning(
                "Fonte ignorada (%.1f MB): %s", peso / 1_000_000, url
            )
            return []
        conteudo = resposta.text or ""
        itens = (
            self._parse_feed(conteudo, url)
            or self._parse_links(conteudo, url)
            or self._parse_texto(conteudo, url)
            or self._parse_titulos(conteudo, url)
        )
        return [i for i in itens if self._valido(i)][: max(0, alvo - ja_coletados)]

    # ---- 1. RSS/Atom -------------------------------------------------
    def _parse_feed(self, conteudo: str, url_base: str) -> list[RawItem]:
        itens: list[RawItem] = []
        try:
            from feedparser import parse  # type: ignore
        except Exception:  # noqa: BLE001
            return itens
        feed = parse(conteudo)
        for entrada in getattr(feed, "entries", [])[:40]:
            titulo = (getattr(entrada, "title", "") or "").strip()
            link = (getattr(entrada, "link", "") or "").strip()
            resumo = (getattr(entrada, "summary", "") or "").strip()
            if not titulo or not link:
                continue
            publicado = getattr(entrada, "published_parsed", None)
            data = datetime(*publicado[:6], tzinfo=timezone.utc) if publicado else None
            itens.append(self._item(titulo, resumo, link, data, url_base))
        return itens

    # ---- 2. Texto principal (trafilatura) ----------------------------
    def _parse_texto(self, conteudo: str, url_base: str) -> list[RawItem]:
        try:
            import trafilatura  # type: ignore
        except Exception:  # noqa: BLE001
            return []
        texto = trafilatura.extract(conteudo, include_comments=False, favor_precision=True) or ""
        blocos = [b.strip() for b in re.split(r"\n+", texto) if len(b.strip()) >= 45]
        itens: list[RawItem] = []
        for bloco in blocos[:40]:
            itens.append(self._item(bloco, "", url_base, None, url_base))
        return itens

    # ---- 3. Titulos (h1..h5) -----------------------------------------
    def _parse_titulos(self, conteudo: str, url_base: str) -> list[RawItem]:
        itens: list[RawItem] = []
        for bruto in _RE_TITULO.findall(conteudo)[:60]:
            titulo = _limpar(bruto)
            if len(titulo) < 35 or len(titulo) > 220:
                continue
            if titulo.lower() in {"notícias", "noticias", "home", "menu"}:
                continue
            itens.append(self._item(titulo, "", url_base, None, url_base))
        return itens

    # ---- 4. Links de conteudo ----------------------------------------
    def _parse_links(self, conteudo: str, url_base: str) -> list[RawItem]:
        itens: list[RawItem] = []
        vistos: set[str] = set()
        for href, texto_bruto in _RE_ANCHOR.findall(conteudo):
            titulo = _limpar(texto_bruto)
            if len(titulo) < 12 or len(titulo) > 220:
                continue
            if not _RE_LINK_CONTEUDO.search(href):
                continue
            link = urljoin(url_base, href)
            if link in vistos:
                continue
            vistos.add(link)
            itens.append(self._item(titulo, "", link, None, url_base))
        return itens

    # ---- 5. Filtro de ruido ------------------------------------------
    def _valido(self, item: RawItem) -> bool:
        """Descarta paginas de erro/WAF e titulos que sao apenas datas."""
        texto = item.texto_limpo or ""
        if _RE_ERRO.search(texto):
            return False
        if _RE_SO_DATA.search(texto):
            return False
        return True

    # ------------------------------------------------------------------
    def _item(
        self,
        titulo: str,
        resumo: str,
        link: str,
        data: datetime | None,
        url_base: str,
    ) -> RawItem:
        texto = f"{titulo}. {resumo}".strip()
        dominio = urlparse(url_base).netloc
        orgao = classificar_orgao(texto) or orgao_por_dominio(dominio)
        metadados = {
            "classe": "propaganda_publica",
            "veiculo": dominio,
            "origem": "radar",
            "fonte_url": url_base,
            "orgao": orgao,
            "espaco_carac": len(texto),
        }
        return RawItem(
            agente_id="__radar__",
            id_externo=self._hash_id(link or titulo),
            plataforma=PLATAFORMA_WEB,
            tipo=TIPO_NOTICIA,
            texto_limpo=texto,
            data_publicacao=data,
            autor=dominio,
            url=link or url_base,
            alcance=0,
            metadados=metadados,
        )

