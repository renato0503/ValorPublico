from datetime import datetime, timezone

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import (
    TIPO_COMENTARIO,
    TIPO_POSTAGEM,
    PLATAFORMA_YOUTUBE,
    RawItem,
)

logger = get_logger(__name__)


class YouTubeScraper(BaseScraper):
    """Coleta videos, transcricoes e comentarios do YouTube.

    - `yt-dlp`: metadados (titulo, descricao, canal, views, likes) e comentarios,
      decifrando os "rolling ciphers" de encriptacao da Google.
    - `youtube-transcript-api`: transcricao das falas (rica para sentimento),
      respeitando o novo fluxo de `Connection: close` para proxies.
    """

    plataforma = PLATAFORMA_YOUTUBE

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.coletar_transcricao = cfg.get("coletar_transcricao", True)
        self.max_videos = int(cfg.get("max_videos", 5))

    def _ydl_opts(self, comentarios: bool) -> dict:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "ignoreerrors": True,
            "extract_flat": not comentarios,
        }
        if comentarios:
            opts.update({"getcomments": True, "extract_flat": False})
        if self.proxies:
            # yt-dlp aceita um proxy por execucao
            opts["proxy"] = self._proximo_proxy() or self.proxies[0]
        return opts

    def _transcricao(self, video_id: str) -> str:
        if not self.coletar_transcricao:
            return ""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            trechos = api.fetch(video_id, languages=["pt"])
            return " ".join(snippet.text for snippet in trechos)
        except Exception as e:  # noqa: BLE001
            logger.debug("YouTube: sem transcricao para %s: %s", video_id, e)
            return ""

    @staticmethod
    def _data(timestamp) -> datetime | None:
        if not timestamp:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        import yt_dlp

        itens: list[RawItem] = []
        n_videos = min(self.max_videos, max(1, limite // 5))
        for termo in agente.get("termos_de_busca", []):
            try:
                with yt_dlp.YoutubeDL(self._ydl_opts(comentarios=False)) as ydl:
                    info = ydl.extract_info(f"ytsearch{n_videos}:{termo}", download=False)
                for v in (info.get("entries") or [])[:n_videos]:
                    video_id = v.get("id")
                    if not video_id:
                        continue
                    texto = f"{v.get('title') or ''} {v.get('description') or ''}".strip()
                    transcricao = self._transcricao(video_id)
                    if transcricao:
                        texto = f"{texto} {transcricao}".strip()
                    itens.append(
                        RawItem(
                            agente_id=agente["id"],
                            id_externo=video_id,
                            plataforma=self.plataforma,
                            tipo=TIPO_POSTAGEM,
                            texto_limpo=texto,
                            data_publicacao=self._data(v.get("timestamp")),
                            autor=v.get("channel") or "",
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            alcance=int(v.get("view_count") or 0),
                            metadados={
                                "canal": v.get("channel") or "",
                                "likes": int(v.get("like_count") or 0),
                                "categoria": v.get("categories") or [],
                            },
                        )
                    )
                    if self.incluir_comentarios:
                        self._extrair_comentarios(agente, video_id, limite, itens)
                    self._sleep()
            except Exception as e:  # noqa: BLE001
                logger.warning("YouTube: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("YouTube: %d itens para %s", len(itens), agente["id"])
        return itens

    def _extrair_comentarios(
        self, agente: dict, video_id: str, limite: int, itens: list[RawItem]
    ) -> None:
        import yt_dlp

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(self._ydl_opts(comentarios=True)) as ydl:
                info = ydl.extract_info(url, download=False)
            comentarios = info.get("comments") or []
            for c in comentarios[:limite]:
                autor = c.get("author") or ""
                itens.append(
                    RawItem(
                        agente_id=agente["id"],
                        id_externo=f"{video_id}_{c.get('id')}",
                        plataforma=self.plataforma,
                        tipo=TIPO_COMENTARIO,
                        texto_limpo=c.get("text") or "",
                        data_publicacao=self._data(c.get("timestamp")),
                        autor=autor,
                        url=url,
                        alcance=int(c.get("like_count") or 0),
                    )
                )
        except Exception as e:  # noqa: BLE001
            logger.debug("YouTube: sem comentarios p/ %s: %s", video_id, e)