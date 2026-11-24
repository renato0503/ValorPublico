"""Navegador do projeto (plano 19): Playwright (+ Patchright/Camoufox em modo stealth).

Este modulo e a "fabrica" de sessao de navegador usada por:
  - `previa_publica.py`  (N2: meta tags `og:*` de link publico)
  - `receitas.py`        (N1: execucao de receita deterministica)
  - `evidencia.py`       (N3/N4: screenshot, PDF e sha256)
  - `coletores redes`    (N8/N9: posts publicos + conta logada do proprio agente)

Salvaguardas do modo stealth (19 §3.1) — implementadas aqui de forma central:
  1. flag `NAVEGADOR_STEALTH` (on nos dois apps);
  2. nunca login de conta falsa/terceira; ao ver parede de login ou CAPTCHA, PARAR e
     registrar (espera 24 h antes de tentar de novo);
  3. ritmo: <= 1 pagina a cada 5–10 s por dominio; <= 30 paginas por agente/dia nas redes;
     sem proxy pago;
  4. conta logada do proprio agente: permitida (flag `NAVEGADOR_CONTA_PROPRIA`), sem
     senha em texto puro no repo (reutiliza o perfil/sessao do navegador do dono);
  5. log de cada sessao (domínio, URL, resultado, bloqueio);
  6. desligamento imediato em bloqueio persistente.

Nao ha login automatico, nem cookies de terceiros, nem resolucao de CAPTCHA.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from cerra_nucleo.core.logger import get_logger

logger = get_logger(__name__)

USER_AGENT_IDENTIFICADO = (
    "CerraClippingBot/1.0 (+https://github.com/renato0503/CerraClipping; "
    "contato: gestor.renatorosa@gmail.com)"
)

# Intervalo minimo entre paginas do mesmo dominio (segundos).
PAUSA_MINIMO = 5.0
PAUSA_MAXIMO = 10.0
# Limite de paginas por agente/dia nas redes.
LIMITE_PAGINAS_AGENTE_DIA = 30
# Tempo de "espera" apos detectar login/CAPTCHA (24 h).
ESPERA_BLOQUEIO_HORAS = 24

# Padrões que caracterizam parede de login ou CAPTCHA.
RE_CAPTCHA = re.compile(
    r"(captcha|recaptcha|hcaptcha|hcaptcha|g-recaptcha|are you a robot|"
    r"verify you are human|unusual traffic|acesso negado|access denied|"
    r"confirme que voc[eê] n[aã]o [eé] um rob[oô])",
    re.IGNORECASE,
)
RE_LOGIN = re.compile(
    r"(entrar no (?:instagram|facebook|tiktok|twitter|x)|log in to|sign in|"
    r"fa[cç]a login|entrar com (?:google|facebook|apple)|"
    r"apenas para usu[aá]rios (?:logados|autenticados))",
    re.IGNORECASE,
)


class BloqueioDetectado(RuntimeError):
    """A pagina pediu login ou CAPTCHA: o coletor PARA (19 §3.1.2)."""

    def __init__(self, url: str, tipo: str) -> None:
        super().__init__(f"Bloqueio '{tipo}' em {url}")
        self.url = url
        self.tipo = tipo


class SessaoNavegador:
    """Sessao de navegador com ritmo por dominio, robots.txt e log de sessoes."""

    def __init__(
        self,
        *,
        stealth: bool = False,
        conta_propria: bool = False,
        headless: bool = True,
        timeout_ms: int = 30000,
        respeitar_robots: bool = True,
        user_agent: str = USER_AGENT_IDENTIFICADO,
        log_path: Path | None = None,
    ) -> None:
        self.stealth = bool(stealth)
        self.conta_propria = bool(conta_propria)
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.respeitar_robots = respeitar_robots
        self.user_agent = user_agent
        self.log_path = log_path
        self._playwright = None
        self._browser = None
        self._context = None
        self._ultimo_acesso: dict[str, float] = {}
        self._bloqueios: dict[str, float] = {}
        self._paginas_agente_dia: dict[str, int] = {}
        self._dia = datetime.now(timezone.utc).date().isoformat()
        self.sessoes: list[dict] = []

    # ------------------------------------------------------------------
    # Ritmo e bloqueios
    # ------------------------------------------------------------------
    def _esperar_turno(self, dominio: str) -> None:
        """Garante >= PAUSA_MINIMO desde o ultimo acesso ao dominio."""
        agora = time.monotonic()
        anterior = self._ultimo_acesso.get(dominio)
        if anterior is not None:
            espera = PAUSA_MINIMO - (agora - anterior)
            if espera > 0:
                logger.info("Ritmo: %ss antes de %s", round(espera, 1), dominio)
                time.sleep(espera)
        self._ultimo_acesso[dominio] = time.monotonic()

    def bloqueado_ate(self, dominio: str) -> float:
        """Epoch do fim da espera imposed por um bloqueio anterior (0 = livre)."""
        return self._bloqueios.get(dominio, 0.0)

    def registrar_bloqueio(self, url: str, tipo: str) -> None:
        dominio = _dominio(url)
        ate = time.time() + ESPERA_BLOQUEIO_HORAS * 3600
        self._bloqueios[dominio] = ate
        self.registrar_sessao(url, resultado="bloqueio", detalhe=tipo)
        logger.warning(
            "Bloqueio %s em %s: parei e nao tento de novo por %dh.",
            tipo, url, ESPERA_BLOQUEIO_HORAS,
        )

    def consumir_limite_agente(self, agente_id: str) -> bool:
        """Reserva uma pagina do limite diario do agente. False se esgotou."""
        hoje = datetime.now(timezone.utc).date().isoformat()
        if hoje != self._dia:
            self._dia = hoje
            self._paginas_agente_dia = {}
        usado = self._paginas_agente_dia.get(agente_id, 0)
        if usado >= LIMITE_PAGINAS_AGENTE_DIA:
            return False
        self._paginas_agente_dia[agente_id] = usado + 1
        return True

    # ------------------------------------------------------------------
    # Robots.txt
    # ------------------------------------------------------------------
    def robots_permite(self, url: str) -> bool:
        """Consulta o robots.txt do dominio. Fora do modo stealth, e obrigatorio."""
        if self.stealth or not self.respeitar_robots:
            return True
        dominio = _dominio(url)
        try:
            from urllib.request import urlopen, Request

            req = Request(f"https://{dominio}/robots.txt", headers={"User-Agent": self.user_agent})
            with urlopen(req, timeout=15) as resp:  # noqa: S310
                corpo = resp.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return True  # sem robots.txt -> permitido
        parser = RobotFileParser()
        parser.parse(corpo.splitlines())
        return parser.can_fetch(self.user_agent, url)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def __enter__(self) -> "SessaoNavegador":
        self.abrir()
        return self

    def __exit__(self, *_) -> None:
        self.fechar()

    def abrir(self) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        if self.stealth:
            self._browser = self._abrir_stealth()
        else:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
        self._context = self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
            ignore_https_errors=True,
        )
        if self.conta_propria:
            self._context = self._abrir_conta_propria(self._context)

    def _abrir_stealth(self):
        """Patchright (drop-in do Playwright) ou Camoufox, se instalados."""
        try:
            from patchright.sync_api import sync_playwright as pw_stealth

            self._playwright = pw_stealth().start()
            return self._playwright.chromium.launch(headless=self.headless)
        except Exception as exc:  # noqa: BLE001
            logger.info("Patchright indisponivel (%s); usando Chromium comum.", exc)
        try:
            from camoufox.sync_api import Camoufox

            return Camoufox(headless=self.headless).launch()  # pragma: no cover
        except Exception as exc:  # noqa: BLE001
            logger.info("Camoufox indisponivel (%s); usando Chromium comum.", exc)
            return self._playwright.chromium.launch(headless=self.headless)

    def _abrir_conta_propria(self, context):
        """Reaproveita o perfil do navegador do dono (conta logada do agente).

        Nao ha senha no repositorio: o perfil fica no disco da maquina e e aberto
        apenas em modo visivel (headless=False) para o dono confirmar o login quando
        a sessao expirar. Sem cookies de terceiros.
        """
        perfil = Path.home() / ".cerra_clipping" / "perfil_agente"
        perfil.mkdir(parents=True, exist_ok=True)
        try:
            from playwright.sync_api import sync_playwright

            if self._playwright is None:
                self._playwright = sync_playwright().start()
            contexto = self._playwright.chromium.launch_persistent_context(
                str(perfil),
                headless=False,
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 900},
                locale="pt-BR",
            )
            logger.info("Conta propria: perfil persistente aberto em %s", perfil)
            return contexto
        except Exception as exc:  # noqa: BLE001
            logger.warning("Nao foi possivel abrir o perfil da conta propria: %s", exc)
            return context

    def fechar(self) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = None
        self._browser = None
        self._playwright = None

    # ------------------------------------------------------------------
    # Navegacao
    # ------------------------------------------------------------------
    def abrir_pagina(self, url: str, agente_id: str | None = None, wait_ms: int = 1500):
        """Abre uma pagina publica e devolve o objeto `page` do Playwright.

        Levanta `BloqueioDetectado` se a pagina pedir login ou CAPTCHA.
        """
        dominio = _dominio(url)
        if self.bloqueado_ate(dominio) > time.time():
            raise BloqueioDetectado(url, "espera_ativa")
        if not self.robots_permite(url):
            self.registrar_sessao(url, resultado="bloqueado_robots")
            raise BloqueioDetectado(url, "robots.txt")
        if agente_id and not self.consumir_limite_agente(agente_id):
            self.registrar_sessao(url, resultado="limite_diario")
            raise BloqueioDetectado(url, "limite_diario_agente")

        self._esperar_turno(dominio)
        page = self._context.new_page()
        try:
            resposta = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            html = page.content()
            self._verificar_bloqueio(url, html)
            self.registrar_sessao(url, resultado="ok", status=getattr(resposta, "status", None))
            return page
        except BloqueioDetectado:
            raise
        except Exception as exc:  # noqa: BLE001
            self.registrar_sessao(url, resultado="erro", detalhe=str(exc)[:200])
            raise

    def _verificar_bloqueio(self, url: str, html: str) -> None:
        if RE_CAPTCHA.search(html):
            self.registrar_bloqueio(url, "captcha")
            raise BloqueioDetectado(url, "captcha")
        if RE_LOGIN.search(html):
            self.registrar_bloqueio(url, "login")
            raise BloqueioDetectado(url, "login")

    # ------------------------------------------------------------------
    # Log das sessoes (19 §3.1.5)
    # ------------------------------------------------------------------
    def registrar_sessao(self, url: str, resultado: str, status: int | None = None, detalhe: str = "") -> None:
        registro = {
            "quando": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "dominio": _dominio(url),
            "resultado": resultado,
            "status": status,
            "detalhe": detalhe,
            "stealth": self.stealth,
            "conta_propria": self.conta_propria,
        }
        self.sessoes.append(registro)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _dominio(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""
    return host[4:] if host.startswith("www.") else host


@dataclass
class Evidencia:
    """Print com data (N4): screenshot + PDF + sha256 da pagina."""

    url: str
    coletado_em: str
    screenshot: str = ""
    pdf: str = ""
    sha256: str = ""
    titulo: str = ""
    metadados: dict = field(default_factory=dict)


def sha256_texto(texto: str) -> str:
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()
