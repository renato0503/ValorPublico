import glob
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import PLATAFORMA_YOUTUBE, TIPO_POSTAGEM, RawItem

logger = get_logger(__name__)


class YouTubeScraper(BaseScraper):
    """Coleta videos do YouTube por busca do nome do agente.

    Usa `yt-dlp` via CLI (subprocess) porque a API Python trava sem timeout.
    Transcreve as falas com as legendas automaticas do YouTube (mesmo parser
    do scraper de TV). A busca usa apenas o primeiro termo do agente (nome
    base), suficiente para encontrar videos que citam o parlamentar.
    """

    plataforma = PLATAFORMA_YOUTUBE

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.coletar_transcricao = cfg.get("coletar_transcricao", True)
        self.max_videos = int(cfg.get("max_videos", 5))
        # Cache por execucao: 1x por termo de busca / video.
        self._cache_videos: dict[str, list[dict]] = {}
        self._cache_transcricao: dict[str, str] = {}

    def _buscar(self, termo: str, n: int) -> list[dict]:
        if termo in self._cache_videos:
            return self._cache_videos[termo]
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist", "--skip-download", "--no-warnings",
            "--playlist-end", str(n),
            "--socket-timeout", "15", "--retries", "1",
            "--print", "%(id)s\t%(title)s\t%(channel)s\t%(timestamp)s\t%(view_count)s",
            f"ytsearch{n}:{termo}",
        ]
        if self.proxies:
            proxy = self._proximo_proxy() or self.proxies[0]
            cmd[1:1] = ["--proxy", proxy]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            videos: list[dict] = []
            for line in proc.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 5 or not parts[0]:
                    continue
                ts = parts[3]
                videos.append(
                    {
                        "id": parts[0],
                        "title": parts[1],
                        "channel": parts[2],
                        "timestamp": int(ts) if ts not in ("", "NA") else None,
                        "view_count": int(parts[4]) if parts[4].isdigit() else None,
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("YouTube: falha na busca '%s': %s", termo, e)
            videos = []
        self._cache_videos[termo] = videos
        return videos

    def _transcricao(self, video_id: str) -> str:
        if video_id in self._cache_transcricao:
            return self._cache_transcricao[video_id]
        texto = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, "sub")
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--skip-download", "--no-warnings",
                "--write-auto-subs", "--sub-langs", "pt,pt-orig",
                "--sub-format", "vtt",
                "--socket-timeout", "15", "--retries", "1",
                "-o", outtmpl,
                f"https://www.youtube.com/watch?v={video_id}",
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                for arq in glob.glob(os.path.join(tmpdir, "*.vtt")):
                    with open(arq, encoding="utf-8", errors="replace") as f:
                        conteudo = f.read()
                    captions: list[str] = []
                    for bloco in conteudo.split("\n\n"):
                        corpo = [
                            re.sub(r"<[^>]+>", "", l).strip()
                            for l in bloco.splitlines()
                            if l.strip() and "-->" not in l
                            and not l.lower().startswith(("webvtt", "kind:", "language:"))
                        ]
                        if corpo:
                            captions.append(" ".join(corpo))
                    palavras_finais: list[str] = []
                    for capt in captions:
                        palavras = capt.split()
                        n = min(len(palavras_finais), len(palavras))
                        sobreposicao = 0
                        for k in range(n, 0, -1):
                            if palavras_finais[-k:] == palavras[:k]:
                                sobreposicao = k
                                break
                        palavras_finais.extend(palavras[sobreposicao:])
                    texto = " ".join(palavras_finais).replace("\\N", " ").strip()
                    if texto:
                        break
            except Exception as e:  # noqa: BLE001
                logger.debug("YouTube: sem transcricao p/ %s: %s", video_id, e)
        self._cache_transcricao[video_id] = texto
        return texto

    @staticmethod
    def _data(timestamp) -> datetime | None:
        if not timestamp:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        itens: list[RawItem] = []
        termos = [t for t in agente.get("termos_de_busca", []) if t.strip()]
        if not termos:
            return itens
        # Apenas o primeiro termo (nome base) para manter a coleta rapida.
        termo = termos[0]
        n_videos = min(self.max_videos, max(1, limite // 5))
        try:
            for v in self._buscar(termo, n_videos):
                video_id = v.get("id")
                if not video_id:
                    continue
                texto = f"{v.get('title') or ''} {v.get('channel') or ''}".strip()
                if self.coletar_transcricao:
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
                        metadados={"canal": v.get("channel") or ""},
                    )
                )
                self._sleep()
        except Exception as e:  # noqa: BLE001
            logger.warning("YouTube: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("YouTube: %d itens para %s", len(itens), agente["id"])
        return itens