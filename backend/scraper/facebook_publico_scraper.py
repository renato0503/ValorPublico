"""Coletor de Facebook **publico** (N9 do plano 19) — substitui o antigo
`facebook_scraper.py` (que usava cookies de sessao e login de conta alheia).

Diferencas em relacao ao arquivo antigo:
  - **sem cookies de terceiros** e **sem login**;
  - usa a fabrica de navegador do `cerra_nucleo` (Chromium ou, com a flag
    `NAVEGADOR_STEALTH`, Patchright/Camoufox);
  - respeita ritmo por dominio, limite diario por agente e `robots.txt`;
  - **para** ao ver parede de login ou CAPTCHA (19 §3.1.2);
  - pode usar a conta logada do **proprio agente** (flag
    `NAVEGADOR_CONTA_PROPRIA`, liberada pelo dono em 24/11/2026).
"""

from __future__ import annotations

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.scraper.navegador import SessaoNavegador
from cerra_nucleo.scraper.redes_publicas import coletar_link
from config import settings
from scraper.base import BaseScraper
from scraper.models import PLATAFORMA_FACEBOOK, RawItem

logger = get_logger(__name__)

# URLs publicas do Facebook que o coletor aceita.
PREFIXOS = (
    "https://www.facebook.com/",
    "https://facebook.com/",
    "https://m.facebook.com/",
)


class FacebookPublicoScraper(BaseScraper):
    """Le posts publicos do Facebook sem cookie e sem login de terceiros."""

    plataforma = PLATAFORMA_FACEBOOK

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.stealth = bool(cfg.get("stealth", settings.NAVEGADOR_STEALTH))
        self.conta_propria = bool(cfg.get("conta_propria", settings.NAVEGADOR_CONTA_PROPRIA))
        self.max_links = int(cfg.get("max_links", 10))
        self._sessao: SessaoNavegador | None = None

    # ------------------------------------------------------------------
    def _abrir_sessao(self) -> SessaoNavegador:
        if self._sessao is None:
            self._sessao = SessaoNavegador(
                stealth=self.stealth,
                conta_propria=self.conta_propria,
                headless=settings.NAVEGADOR_HEADLESS,
                timeout_ms=settings.NAVEGADOR_TIMEOUT_MS,
            )
            self._sessao.abrir()
        return self._sessao

    def fechar(self) -> None:
        if self._sessao is not None:
            self._sessao.fechar()
            self._sessao = None

    # ------------------------------------------------------------------
    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        """Coleta ate `limite` itens publicos a partir dos links conhecidos.

        Os links vem do buscador (`metadados.links_publicos`) — o scraper nao
        inventa URLs nem faz busca propria.
        """
        links = (agente.get("metadados") or {}).get("links_publicos") or []
        if not links:
            return []
        itens: list[RawItem] = []
        sessao = self._abrir_sessao()
        for url in links[: min(self.max_links, limite)]:
            if len(itens) >= limite:
                break
            if not any(url.startswith(p) for p in PREFIXOS):
                continue
            achado = coletar_link(
                url, sessao, agente_id=str(agente.get("id", "")), conta_propria=self.conta_propria
            )
            if not achado:
                continue
            itens.append(
                RawItem(
                    agente_id=agente["id"],
                    id_externo=self._hash_id(url),
                    plataforma=achado["plataforma"],
                    tipo="Postagem",
                    texto_limpo=achado["texto"] or url,
                    data_publicacao=achado["data"] or None,
                    autor="",
                    url=url,
                    alcance=0,
                    metadados={
                        "origem_coleta": "navegador",
                        "stealth": self.stealth,
                        "conta_propria": achado["conta_propria"],
                        "imagem": achado["imagem"],
                    },
                )
            )
        logger.info("Facebook publico: %d itens para %s", len(itens), agente.get("id"))
        return itens
