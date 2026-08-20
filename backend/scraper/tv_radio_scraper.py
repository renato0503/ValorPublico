from datetime import datetime, timezone

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import (
    TIPO_POSTAGEM,
    PLATAFORMA_RADIO,
    PLATAFORMA_TV,
    RawItem,
)

logger = get_logger(__name__)


class _TranscricaoScraper(BaseScraper):
    """Base para TV/Radio: monitora canais de noticia no YouTube e transcreve
    as falas (via youtube-transcript-api), buscando mencoes aos agentes.

    A transcricao das falas e rica para sentimento e permite capturar
    cobertura audiovisual que nao aparece em texto.
    """

    #: Canal "tipo" usado na URL de busca de uploads (compativel com yt-dlp)
    max_videos_por_canal = 10

    def _ultimos_videos(self, canal: str, limite: int) -> list[dict]:
        import yt_dlp

        n = max(1, min(self.max_videos_por_canal, limite or 1))
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": False,
            "ignoreerrors": True,
            "extract_flat": True,
        }
        if self.proxies:
            opts["proxy"] = self._proximo_proxy() or self.proxies[0]

        url = f"https://www.youtube.com/{canal}/videos"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return (info.get("entries") or [])[:n]

    def _transcricao(self, video_id: str) -> str:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            trechos = api.fetch(video_id, languages=["pt"])
            return " ".join(snippet.text for snippet in trechos)
        except Exception as e:  # noqa: BLE001
            logger.debug("%s: sem transcricao p/ %s: %s", self.plataforma, video_id, e)
            return ""

    @staticmethod
    def _data(timestamp) -> datetime | None:
        if not timestamp:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    def _menciona(self, texto: str, termos: list[str]) -> bool:
        t = texto.lower()
        return any(termo.lower() in t for termo in termos)

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        itens: list[RawItem] = []
        canais = self.canais
        if not canais:
            logger.warning("%s: nenhum canal configurado (TV_CANAIS/RADIO_CANAIS).", self.plataforma)
            return itens
        termos = agente.get("termos_de_busca", [])

        for canal in canais:
            try:
                for v in self._ultimos_videos(canal, limite):
                    video_id = v.get("id")
                    if not video_id:
                        continue
                    transcricao = self._transcricao(video_id)
                    titulo = v.get("title") or ""
                    if not self._menciona(f"{titulo} {transcricao}", termos):
                        continue
                    itens.append(
                        RawItem(
                            agente_id=agente["id"],
                            id_externo=video_id,
                            plataforma=self.plataforma,
                            tipo=TIPO_POSTAGEM,
                            texto_limpo=f"{titulo} {transcricao}".strip(),
                            data_publicacao=self._data(v.get("timestamp")),
                            autor=canal,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            alcance=int(v.get("view_count") or 0),
                            metadados={
                                "canal": canal,
                                "transcricao": True,
                            },
                        )
                    )
                    self._sleep()
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "%s: falha no canal '%s' do agente %s: %s",
                    self.plataforma, canal, agente["id"], e,
                )
        logger.info("%s: %d itens para %s", self.plataforma, len(itens), agente["id"])
        return itens


class TVScraper(_TranscricaoScraper):
    """Monitora canais de TV no YouTube e transcreve as falas dos telejornais."""

    plataforma = PLATAFORMA_TV

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.canais = cfg.get("canais", [])
        self.max_videos_por_canal = int(cfg.get("max_videos_por_canal", 10))


class RadioScraper(_TranscricaoScraper):
    """Monitora canais de radio (webcast/YouTube) e transcreve as falas."""

    plataforma = PLATAFORMA_RADIO

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.canais = cfg.get("canais", [])
        self.max_videos_por_canal = int(cfg.get("max_videos_por_canal", 10))