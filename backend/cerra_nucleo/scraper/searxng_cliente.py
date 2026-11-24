"""Cliente SearXNG (metabuscaopen-source, 100% gratuito e local/auto-hospedado).

Por que: o Google Custom Search JSON API foi encerrado para novos clientes e
esta descontinuado em 01/01/2027; Serper/SerpAPI sao pagos (fora da regra do
dono). O SearXNG consulta os mesmos buscadores de um container efemero no
GitHub Actions (imagem oficial `searxng/searxng`) e devolve JSON quando a
formatacao `json` esta habilitada.

O modulo e 100% opcional: se `SEARXNG_URL` nao estiver definido, quem chama
cai no fallback (ddgs). Nao ha login, cookie de terceiro nem CAPTCHA.

Uso:
    from cerra_nucleo.scraper.searxng_cliente import SearXNGCliente

    cliente = SearXNGCliente("http://localhost:8080")
    resultados = cliente.buscar('"fulano" (site:instagram.com)', 10)
"""

from __future__ import annotations

import json
import time
from urllib.parse import urlparse

import requests

# Motores recomendados para o Brasil (ordem de preferencia do SearXNG).
MOTORES_PADRAO = ("google", "bing", "brave", "duckduckgo", "startpage")

# Payload minimo devolvido pelo SearXNG em /search?format=json.
CAMPOS_RESULTADO = ("title", "url", "content", "engine", "score", "category")


class SearXNGIndisponivel(RuntimeError):
    """O SearXNG nao respondeu (container ausente, JSON desabilitado, etc.)."""


class SearXNGCliente:
    """Cliente HTTP do SearXNG com retry e backoff exponencial."""

    def __init__(
        self,
        url_base: str = "",
        motores: tuple[str, ...] = MOTORES_PADRAO,
        timeout: float = 20.0,
        max_tentativas: int = 3,
        idioma: str = "pt-BR",
        pais: str = "br",
        pausa: float = 1.5,
    ) -> None:
        self.url_base = (url_base or "").rstrip("/")
        self.motores = tuple(m for m in motores if m)
        self.timeout = timeout
        self.max_tentativas = max_tentativas
        self.idioma = idioma
        self.pais = pais
        self.pausa = pausa
        self.consultas = 0
        self._ultimo_resultado: list[dict] = []

    # ------------------------------------------------------------------
    def disponivel(self) -> bool:
        """True se ha URL configurada (checagem real de rede fica a cargo do chamador)."""
        return bool(self.url_base)

    def _params(self, consulta: str, n: int) -> dict:
        params: dict[str, object] = {
            "q": consulta,
            "format": "json",
            "language": self.idioma,
            "safesearch": 0,
        }
        if n:
            params["pageno"] = 1
        if self.motores:
            params["engines"] = ",".join(self.motores)
        return params

    def buscar(self, consulta: str, n: int = 10) -> list[dict]:
        """Executa a consulta e devolve a lista normalizada de resultados.

        Cada resultado: {"titulo", "url", "snippet", "motor", "score"}.
        Levanta `SearXNGIndisponivel` se o servico nao responder.
        """
        if not self.disponivel():
            raise SearXNGIndisponivel("SEARXNG_URL nao configurada")

        url = f"{self.url_base}/search"
        ultimo_erro: Exception | None = None
        for tentativa in range(1, self.max_tentativas + 1):
            try:
                resp = requests.get(
                    url,
                    params=self._params(consulta, n),
                    timeout=self.timeout,
                    headers={
                        "User-Agent": "CerraClipping/1.0 (+https://github.com/renato0503)",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 429:
                    raise SearXNGIndisponivel("SearXNG devolveu 429 (rate limit)")
                resp.raise_for_status()
                dados = self._parse(resp.text)
                self.consultas += 1
                self._ultimo_resultado = dados
                return dados[: max(n, 1)] if n else dados
            except SearXNGIndisponivel:
                raise
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
                if tentativa < self.max_tentativas:
                    time.sleep(self.pausa * (2 ** (tentativa - 1)))
        raise SearXNGIndisponivel(f"SearXNG indisponivel: {ultimo_erro}")

    # ------------------------------------------------------------------
    def _parse(self, texto: str) -> list[dict]:
        """Converte o JSON do SearXNG na lista normalizada."""
        try:
            bruto = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise SearXNGIndisponivel(
                "SearXNG nao devolveu JSON (formatacao json desabilitada?)"
            ) from exc
        if not isinstance(bruto, list):
            raise SearXNGIndisponivel("SearXNG devolveu um payload inesperado")
        saida: list[dict] = []
        for item in bruto:
            if not isinstance(item, dict):
                continue
            link = (item.get("url") or "").strip()
            if not link:
                continue
            saida.append(
                {
                    "titulo": (item.get("title") or "").strip(),
                    "url": link,
                    "snippet": (item.get("content") or "").strip(),
                    "motor": (item.get("engine") or "").strip(),
                    "score": item.get("score") or 0,
                    "host": (urlparse(link).hostname or "").lower(),
                }
            )
        return saida

    def estatisticas(self) -> dict:
        return {"url_base": self.url_base, "consultas": self.consultas, "motores": list(self.motores)}
