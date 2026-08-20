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

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.canais: list[str] = cfg.get("canais", [])
        self.max_videos_por_canal = int(cfg.get("max_videos_por_canal", 10))
        # Cache por execucao: evita re-listar canais e re-transcrever videos
        # para cada um dos 50 agentes (de 50x -> 1x por video unico).
        self._cache_videos: dict[str, list[dict]] = {}
        self._cache_transcricao: dict[str, str] = {}

    def _ultimos_videos(self, canal: str, limite: int) -> list[dict]:
        if canal in self._cache_videos:
            return self._cache_videos[canal]
        import subprocess
        import sys

        n = max(1, min(self.max_videos_por_canal, limite or 1))
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist", "--skip-download", "--no-warnings",
            "--playlist-end", str(n),
            "--socket-timeout", "15", "--retries", "2",
            "--print", "%(id)s\t%(title)s\t%(timestamp)s\t%(view_count)s",
            f"https://www.youtube.com/{canal}/videos",
        ]
        if self.proxies:
            proxy = self._proximo_proxy() or self.proxies[0]
            cmd[1:1] = ["--proxy", proxy]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            videos = []
            for line in proc.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 4 or not parts[0]:
                    continue
                ts = parts[2]
                videos.append(
                    {
                        "id": parts[0],
                        "title": parts[1],
                        "timestamp": int(ts) if ts not in ("", "NA") else None,
                        "view_count": int(parts[3]) if parts[3].isdigit() else None,
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("%s: falha ao listar canal %s: %s", self.plataforma, canal, e)
            videos = []
        self._cache_videos[canal] = videos
        return videos

    def _transcricao(self, video_id: str) -> str:
        if video_id in self._cache_transcricao:
            return self._cache_transcricao[video_id]
        import glob
        import os
        import re
        import subprocess
        import sys
        import tempfile

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
                    # Legendas automaticas do YouTube sao "rolantes": cada cue
                    # repete a linha inteira acumulada. Deduz linhas contidas
                    # na seguinte para obter o texto final sem duplicacao.
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
                    # Legendas "rolantes": cada cue repete trecho anterior.
                    # Une as frases removendo a sobreposicao maxima de palavras.
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
                logger.debug("%s: sem transcricao p/ %s: %s", self.plataforma, video_id, e)
        self._cache_transcricao[video_id] = texto
        return texto

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


class RadioScraper(_TranscricaoScraper):
    """Monitora canais de radio (webcast/YouTube) e transcreve as falas."""

    plataforma = PLATAFORMA_RADIO