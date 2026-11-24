"""Redes sociais via buscador (sem login, so o que o buscador exibe).

Estrategia: para cada agente, consulta um buscador com ``site:`` para as redes
e guarda o que a propria pagina de resultados ja mostra publicamente: titulo,
descricao/snippet, URL e (quando o snippet traz) trecho de comentario. Nao faz
login em rede nenhuma, nao burla CAPTCHA/bloqueio e nao guarda dados de
comentaristas alem do trecho publico (LGPD).

Motores, em ordem de preferencia (configuraveis por env):
  1. **SearXNG** (container proprio no Actions; sem chave, sem custo) — padrao
  2. DuckDuckGo via pacote `ddgs` (sem chave) — reserva
  3. ~~Google CSE / Serper / SerpAPI~~ — **removidos**: o CSE foi encerrado
     para novos clientes e descontinua em 01/01/2027; Serper/SerpAPI sao pagos
     (fora da regra do dono).

Orcamento: no maximo ``BUSCA_SOCIAL_MAX_CONSULTAS`` por execucao, com rodizio
(metade dos agentes por dia) e dedup por URL. O numero de consultas por motor
e registrado em ``estatisticas()``.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from cerra_nucleo.scraper.searxng_cliente import SearXNGCliente, SearXNGIndisponivel
from config import settings
from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import TIPO_COMENTARIO, TIPO_POSTAGEM, RawItem

logger = get_logger(__name__)

PLATAFORMA = "Redes"

# dominio -> plataforma exibida
DOMINIOS_REDE = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "fb.watch": "Facebook",
    "x.com": "Twitter",
    "twitter.com": "Twitter",
    "tiktok.com": "TikTok",
    "threads.net": "Threads",
    "threads.com": "Threads",
    "kwai.com": "Kwai",
    "kwai-video.com": "Kwai",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
}

# plataformas efetivamente tratadas como "rede social" pelo painel/agregado
PLATAFORMAS_SOCIAIS = {"Instagram", "Facebook", "Twitter", "TikTok", "Threads", "Kwai"}

URLS_REDE = " OR ".join(
    f"site:{d}" for d in (
        "instagram.com", "facebook.com", "x.com", "twitter.com",
        "tiktok.com", "threads.net", "kwai.com",
    )
)

RE_COMENTARIO = re.compile(
    r"\b(comentou|coment[aá]rio|coment[aá]rios|respondeu|respostas?|"
    r"replying to|replied|reagiu)\b",
    re.IGNORECASE,
)

RE_RELATIVO = re.compile(
    r"h[aá]\s+(?:cerca de\s+)?(\d+)\s*"
    r"(min(?:uto)?s?|h(?:ora)?s?|dias?|semanas?|m[eê]s(?:es)?|anos?)",
    re.IGNORECASE,
)


def _sem_acento(texto: str) -> str:
    from unicodedata import normalize

    return (
        normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def plataforma_da_url(url: str) -> str | None:
    """Mapeia a URL para a plataforma social, ou None se nao for rede."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return None
    host = host[4:] if host.startswith("www.") else host
    for dominio, plataforma in DOMINIOS_REDE.items():
        if host == dominio or host.endswith("." + dominio):
            return plataforma
    return None


def parece_comentario(texto: str) -> bool:
    """Heuristica: o snippet indica um comentario/resposta publica.

    Evita falso positivo de bio de perfil ("Fulano on Instagram: \\"bio\\""):
    o trecho entre aspas so conta como comentario quando ha verbo de fala.
    """
    if not texto:
        return False
    if RE_COMENTARIO.search(texto):
        return True
    if re.search(r"\b(disse|escreveu|afirmou|declarou)\s*:\s*[\"“']", texto, re.IGNORECASE):
        return True
    return False


def extrair_data_relativa(texto: str, agora: datetime | None = None) -> datetime | None:
    """Converte 'ha 3 dias', 'ontem', etc. em datetime UTC (aprox.)."""
    if not texto:
        return None
    agora = agora or datetime.now(timezone.utc)
    low = _sem_acento(texto)
    if re.search(r"\bhoje\b|\bagora\b|\bha poucos\b", low):
        return agora
    if re.search(r"\bontem\b", low):
        return agora - timedelta(days=1)
    m = RE_RELATIVO.search(low)
    if not m:
        return None
    qtd = int(m.group(1))
    unidade = m.group(2)
    if unidade.startswith("min"):
        delta = timedelta(minutes=qtd)
    elif unidade.startswith("h"):
        delta = timedelta(hours=qtd)
    elif unidade.startswith("dia"):
        delta = timedelta(days=qtd)
    elif unidade.startswith("semana"):
        delta = timedelta(weeks=qtd)
    elif unidade.startswith("m"):  # mes/meses
        delta = timedelta(days=30 * qtd)
    else:  # ano
        delta = timedelta(days=365 * qtd)
    return agora - delta


def classificar_tipo(titulo: str, snippet: str) -> str:
    texto = f"{titulo} {snippet}"
    return TIPO_COMENTARIO if parece_comentario(texto) else TIPO_POSTAGEM


def calcular_confianca(nome: str, titulo: str, snippet: str) -> str:
    """alta se o nome aparece no snippet; media se so parte; baixa se so no titulo."""
    nome_norm = _sem_acento(nome)
    corpo = _sem_acento(snippet or "")
    cabeca = _sem_acento(titulo or "")
    if nome_norm and nome_norm in corpo:
        return "alta"
    partes = [p for p in nome_norm.split() if len(p) > 2 and p not in {"dos", "das", "de"}]
    if partes and all(p in corpo for p in partes):
        return "alta"
    if partes and any(p in corpo for p in partes):
        return "media"
    if nome_norm and nome_norm in cabeca:
        return "media"
    if partes and all(p in cabeca for p in partes):
        return "baixa"
    return "baixa"


class BuscaSocialScraper(BaseScraper):
    """Descobre posts/comentarios publicos de redes via buscador."""

    plataforma = PLATAFORMA

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.max_consultas = int(cfg.get("max_consultas", settings.BUSCA_SOCIAL_MAX_CONSULTAS))
        self.max_resultados = int(cfg.get("max_resultados", settings.BUSCA_SOCIAL_MAX_RESULTADOS))
        self.rodizio = bool(cfg.get("rodizio", settings.BUSCA_SOCIAL_RODIZIO))
        self.regiao = cfg.get("regiao", settings.BUSCA_SOCIAL_REGIAO)
        self._lock = threading.Lock()
        self._consultas = 0
        self._urls_vistas: set[str] = set()
        self._por_motor: dict[str, int] = {}
        self._cache_consulta: dict[str, list[dict]] = {}
        self._searxng: SearXNGCliente | None = None

    # ---------------- motores ----------------
    def _motor(self) -> str:
        """Motor em uso: SearXNG (padrao) ou ddgs (reserva)."""
        if settings.SEARXNG_URL:
            return "searxng"
        return "ddgs"

    def _consultar(self, consulta: str, n: int) -> list[dict]:
        motor = self._motor()
        try:
            if motor == "searxng":
                res = self._searxng(consulta, n)
            else:
                res = self._ddgs(consulta, n)
        except Exception as e:  # noqa: BLE001
            logger.warning("Busca social (%s) falhou para %r: %s", motor, consulta, e)
            res = []
        with self._lock:
            self._por_motor[motor] = self._por_motor.get(motor, 0) + 1
        return res

    def _searxng(self, consulta: str, n: int) -> list[dict]:
        """Consulta o SearXNG (motor nº 1)."""
        cliente = self._cliente_searxng()
        resultados = cliente.buscar(consulta, n)
        return [
            {
                "titulo": r.get("titulo", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
                "thumb": r.get("imagem") or r.get("img_src") or "",
            }
            for r in resultados
        ]

    def _cliente_searxng(self) -> SearXNGCliente:
        """Instancia (e reaproveita) o cliente SearXNG."""
        with self._lock:
            if self._searxng is None:
                self._searxng = SearXNGCliente(
                    url_base=settings.SEARXNG_URL,
                    motores=settings.SEARXNG_MOTORES,
                    timeout=settings.SEARXNG_TIMEOUT,
                )
            return self._searxng

    def _ddgs(self, consulta: str, n: int) -> list[dict]:
        from ddgs import DDGS

        try:
            with DDGS(timeout=20) as d:
                res = d.text(consulta, max_results=max(n, 1), region=self.regiao)
        except Exception as e:  # noqa: BLE001
            # Sem resultados / rate limit: nao e erro fatal, apenas 0 itens.
            logger.info("ddgs sem resultados (%r): %s", consulta, e)
            res = []
        return [
            {"titulo": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in res or []
        ]

    # ---------------- orcamento / rodizio ----------------
    def _na_rodada(self, agente: dict) -> bool:
        if not self.rodizio:
            return True
        aid = str(agente.get("id", ""))
        dia = datetime.now(timezone.utc).timetuple().tm_yday
        return (sum(aid.encode("utf-8")) % 2) == (dia % 2)

    def _consumir_orcamento(self) -> bool:
        with self._lock:
            if self._consultas >= self.max_consultas:
                return False
            self._consultas += 1
            return True

    def estatisticas(self) -> dict:
        with self._lock:
            return {
                "motor": self._motor(),
                "consultas": self._consultas,
                "limite": self.max_consultas,
                "por_motor": dict(self._por_motor),
            }

    # ---------------- coleta ----------------
    def _consultas_agente(self, nome: str) -> list[str]:
        return [
            f'"{nome}" ({URLS_REDE})',
            f'"{nome}" comentou OR comentários OR respondeu',
        ]

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        nome = (agente.get("nome_urna") or "").strip()
        if not nome:
            termos = [t for t in agente.get("termos_de_busca", []) if t.strip()]
            nome = termos[0] if termos else ""
        if not nome or not self._na_rodada(agente):
            return []

        itens: list[RawItem] = []
        for consulta in self._consultas_agente(nome):
            if len(itens) >= limite:
                break
            if not self._consumir_orcamento():
                logger.info("Busca social: orcamento de %d consultas atingido.", self.max_consultas)
                break
            resultados = self._consultar(consulta, self.max_resultados)
            for r in resultados:
                url = (r.get("url") or "").strip()
                plataforma = plataforma_da_url(url)
                if not plataforma or plataforma not in PLATAFORMAS_SOCIAIS:
                    continue
                with self._lock:
                    if url in self._urls_vistas:
                        continue
                    self._urls_vistas.add(url)
                titulo = (r.get("titulo") or "").strip()
                snippet = (r.get("snippet") or "").strip()
                tipo = classificar_tipo(titulo, snippet)
                confianca = calcular_confianca(nome, titulo, snippet)
                data = extrair_data_relativa(snippet) or extrair_data_relativa(titulo)
                texto = " — ".join(p for p in (titulo, snippet) if p).strip()
                itens.append(
                    RawItem(
                        agente_id=agente["id"],
                        id_externo=self._hash_id(url),
                        plataforma=plataforma,
                        tipo=tipo,
                        texto_limpo=texto or url,
                        data_publicacao=data or datetime.now(timezone.utc),
                        autor="",
                        url=url,
                        alcance=0,
                        metadados={
                            "origem_coleta": "busca",
                            "motor": self._motor(),
                            "snippet": snippet,
                            "titulo": titulo,
                            "confianca": confianca,
                            "data_estimada": data is None,
                            "consulta": consulta,
                        },
                    )
                )
                if len(itens) >= limite:
                    break
        logger.info(
            "Busca social: %d itens para %s (motor=%s, consultas=%d/%d)",
            len(itens), agente["id"], self._motor(), self._consultas, self.max_consultas,
        )
        return itens
