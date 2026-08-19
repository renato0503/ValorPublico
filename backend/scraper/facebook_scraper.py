from pathlib import Path

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import (
    TIPO_COMENTARIO,
    TIPO_POSTAGEM,
    PLATAFORMA_FACEBOOK,
    RawItem,
)

logger = get_logger(__name__)


class FacebookScraper(BaseScraper):
    """Coleta posts e comentarios de paginas do Facebook via `facebook-scraper`.

    O Facebook bloqueia fortemente scraping; usa cookies.txt (`cookies_file`)
    para autenticar. A busca e feita pelo nome da pagina (termo tratado como
    slug da pagina), sem API oficial.
    """

    plataforma = PLATAFORMA_FACEBOOK

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.cookies_file = cfg.get("cookies_file", "")

    def _opcoes(self) -> dict:
        opts = {"posts_per_page": 25, "options": {"comments": True}}
        if self.cookies_file and Path(self.cookies_file).exists():
            opts["cookies"] = self.cookies_file
        return opts

    @staticmethod
    def _slug_pagina(termo: str) -> str:
        return termo.strip().lower().replace(" ", "")

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        from facebook_scraper import get_posts

        itens: list[RawItem] = []
        opcoes = self._opcoes()
        for termo in agente.get("termos_de_busca", []):
            pagina = self._slug_pagina(termo)
            try:
                for post in get_posts(pagina, **opcoes):
                    if len(itens) >= limite:
                        break
                    itens.append(
                        RawItem(
                            agente_id=agente["id"],
                            id_externo=post.get("post_id") or self._hash_id(pagina + post.get("time", "").isoformat()),
                            plataforma=self.plataforma,
                            tipo=TIPO_POSTAGEM,
                            texto_limpo=post.get("text") or "",
                            data_publicacao=post.get("time"),
                            autor=post.get("username") or pagina,
                            url=post.get("post_url") or "",
                            alcance=int(post.get("likes") or 0),
                            metadados={
                                "likes": int(post.get("likes") or 0),
                                "comments": int(post.get("comments") or 0),
                                "shares": int(post.get("shares") or 0),
                            },
                        )
                    )
                    if self.incluir_comentarios and post.get("comments_full"):
                        for c in post["comments_full"]:
                            itens.append(
                                RawItem(
                                    agente_id=agente["id"],
                                    id_externo=c.get("comment_id") or self._hash_id(pagina + c.get("comment_text", "")),
                                    plataforma=self.plataforma,
                                    tipo=TIPO_COMENTARIO,
                                    texto_limpo=c.get("comment_text") or "",
                                    data_publicacao=c.get("comment_time"),
                                    autor=c.get("commenter_name") or "",
                                    url=post.get("post_url") or "",
                                    alcance=0,
                                )
                            )
                self._sleep()
            except Exception as e:  # noqa: BLE001
                logger.warning("Facebook: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("Facebook: %d itens para %s", len(itens), agente["id"])
        return itens