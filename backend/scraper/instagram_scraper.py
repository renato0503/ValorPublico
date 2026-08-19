from pathlib import Path

import instaloader

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import (
    TIPO_COMENTARIO,
    TIPO_POSTAGEM,
    PLATAFORMA_INSTAGRAM,
    RawItem,
)

logger = get_logger(__name__)


class InstagramScraper(BaseScraper):
    """Coleta posts e comentarios do Instagram via `instaloader`.

    Usa cookie de sessao injetado (`session_file`) para evitar bloqueios;
    o login classico (username/password) e o fallback.
    """

    plataforma = PLATAFORMA_INSTAGRAM

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.username = cfg.get("username", "")
        self.password = cfg.get("password", "")
        self.session_file = cfg.get("session_file", "")
        self._logado = False
        self._loader: instaloader.Instaloader | None = None

    def _login(self) -> instaloader.Instaloader:
        if self._logado and self._loader is not None:
            return self._loader

        loader = instaloader.Instaloader(
            quiet=True,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=self.incluir_comentarios,
            save_metadata=False,
        )
        session_path = Path(self.session_file)
        try:
            if self.session_file and session_path.exists():
                loader.load_session_from_file(self.username, str(session_path))
                logger.info("Instagram: sessao carregada de %s", session_path)
            elif self.username and self.password:
                loader.login(self.username, self.password)
                if self.session_file:
                    loader.save_session_to_file(str(session_path))
                    logger.info("Instagram: sessao salva em %s", session_path)
            else:
                logger.warning("Instagram: sem credenciais/sessao, tentando modo anonimo.")
        except Exception as e:  # noqa: BLE001
            logger.error("Instagram: falha de autenticacao: %s", e)
            raise

        self._loader = loader
        self._logado = True
        return loader

    @staticmethod
    def _normalizar_usuario(termo: str) -> str:
        return termo.strip().lower().replace(" ", "")

    def _posts_do_perfil(self, loader, username: str, limite: int):
        perfil = instaloader.Profile.from_username(loader.context, username)
        n = 0
        for post in perfil.get_posts():
            if n >= limite:
                break
            yield post
            n += 1

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        loader = self._login()
        itens: list[RawItem] = []
        for termo in agente.get("termos_de_busca", []):
            usuario = self._normalizar_usuario(termo)
            try:
                for post in self._posts_do_perfil(loader, usuario, limite):
                    itens.append(
                        RawItem(
                            agente_id=agente["id"],
                            id_externo=post.shortcode,
                            plataforma=self.plataforma,
                            tipo=TIPO_POSTAGEM,
                            texto_limpo=post.caption or "",
                            data_publicacao=post.date_utc,
                            autor=post.owner_username,
                            url=f"https://www.instagram.com/p/{post.shortcode}/",
                            alcance=int(post.likes + post.comments),
                            metadados={
                                "likes": int(post.likes),
                                "comentarios": int(post.comments),
                                "video": bool(post.is_video),
                            },
                        )
                    )
                    if self.incluir_comentarios:
                        for c in post.get_comments():
                            itens.append(
                                RawItem(
                                    agente_id=agente["id"],
                                    id_externo=str(c.id),
                                    plataforma=self.plataforma,
                                    tipo=TIPO_COMENTARIO,
                                    texto_limpo=c.text or "",
                                    data_publicacao=c.created_at_utc,
                                    autor=c.owner.username if c.owner else "",
                                    url=f"https://www.instagram.com/p/{post.shortcode}/",
                                    alcance=0,
                                )
                            )
                self._sleep()
            except Exception as e:  # noqa: BLE001
                logger.warning("Instagram: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("Instagram: %d itens para %s", len(itens), agente["id"])
        return itens