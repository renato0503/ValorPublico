import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import PLATAFORMA_YOUTUBE, TIPO_COMENTARIO, TIPO_POSTAGEM, RawItem

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
        self.coletar_comentarios = cfg.get("coletar_comentarios", True)
        self.max_comentarios = int(cfg.get("max_comentarios", 15))
        self.max_videos = int(cfg.get("max_videos", 5))
        # Cache por execucao: 1x por termo de busca / video.
        self._cache_videos: dict[str, list[dict]] = {}
        self._cache_transcricao: dict[str, str] = {}
        self._cache_comentarios: dict[str, list[dict]] = {}

    def _buscar(self, termo: str, n: int) -> list[dict]:
        if termo in self._cache_videos:
            return self._cache_videos[termo]
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist", "--skip-download", "--no-warnings",
            "--playlist-end", str(n),
            "--socket-timeout", "15", "--retries", "1",
            "--print", "%(id)s\t%(title)s\t%(channel)s\t%(timestamp)s\t%(view_count)s\t%(duration)s",
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
                        "duration": int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else None,
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

    def _comentarios(self, video_id: str, n: int) -> list[dict]:
        """Comentarios publicos do video via yt-dlp (getcomments)."""
        if not self.coletar_comentarios or n <= 0:
            return []
        if video_id in self._cache_comentarios:
            return self._cache_comentarios[video_id]
        url = f"https://www.youtube.com/watch?v={video_id}"
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--skip-download", "--no-warnings", "--dump-single-json",
            "--write-comments",
            "--extractor-args", f"youtube:max_comments={n},all,{n};comment_sort=top",
            "--socket-timeout", "20", "--retries", "1",
            url,
        ]
        comentarios: list[dict] = []
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            info = json.loads(proc.stdout or "{}")
            for c in (info.get("comments") or [])[:n]:
                texto = (c.get("text") or "").strip()
                if not texto:
                    continue
                comentarios.append(
                    {
                        "id": c.get("id") or "",
                        "autor": c.get("author") or "",
                        "texto": texto,
                        "curtidas": int(c.get("like_count") or 0),
                        "timestamp": c.get("timestamp"),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug("YouTube: sem comentarios p/ %s: %s", video_id, e)
        self._cache_comentarios[video_id] = comentarios
        return comentarios

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        itens: list[RawItem] = []
        termos = [t for t in agente.get("termos_de_busca", []) if t.strip()]
        if not termos:
            return itens
        # Apenas o primeiro termo (nome base) para manter a coleta rapida.
        termo = termos[0]
        n_videos = min(self.max_videos, max(1, limite // 5))
        try:
            videos = self._buscar(termo, n_videos)
            for indice, v in enumerate(videos):
                video_id = v.get("id")
                if not video_id:
                    continue
                texto = f"{v.get('title') or ''} {v.get('channel') or ''}".strip()
                if self.coletar_transcricao:
                    transcricao = self._transcricao(video_id)
                    if transcricao:
                        texto = f"{texto} {transcricao}".strip()
                data_video = self._data(v.get("timestamp"))
                itens.append(
                    RawItem(
                        agente_id=agente["id"],
                        id_externo=video_id,
                        plataforma=self.plataforma,
                        tipo=TIPO_POSTAGEM,
                        texto_limpo=texto,
                        data_publicacao=data_video,
                        autor=v.get("channel") or "",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        alcance=int(v.get("view_count") or 0),
                        metadados={
                            "canal": v.get("channel") or "",
                            "duracao_seg": int(v.get("duration") or 0),
                            "duracao_min": round(int(v.get("duration") or 0) / 60, 1),
                        },
                    )
                )
                # Comentarios publicos apenas dos primeiros videos (custo alto).
                if self.coletar_comentarios and indice < 2:
                    for c in self._comentarios(video_id, self.max_comentarios):
                        texto_c = c["texto"]
                        if not texto_c:
                            continue
                        itens.append(
                            RawItem(
                                agente_id=agente["id"],
                                id_externo=f"{video_id}-c-{c['id'] or self._hash_id(texto_c)[:8]}",
                                plataforma=self.plataforma,
                                tipo=TIPO_COMENTARIO,
                                texto_limpo=texto_c,
                                data_publicacao=self._data(c.get("timestamp")) or data_video,
                                autor=c.get("autor") or "",
                                url=f"https://www.youtube.com/watch?v={video_id}"
                                    + (f"&lc={c['id']}" if c.get("id") else ""),
                                alcance=int(c.get("curtidas") or 0),
                                metadados={"video_id": video_id, "titulo_video": v.get("title") or ""},
                            )
                        )
                self._sleep()
        except Exception as e:  # noqa: BLE001
            logger.warning("YouTube: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("YouTube: %d itens para %s", len(itens), agente["id"])
        return itens