import json
import random
import time
from pathlib import Path
from urllib.parse import quote

from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import TIPO_COMENTARIO, TIPO_POSTAGEM, PLATAFORMA_FACEBOOK, RawItem

logger = get_logger(__name__)

# facebook-scraper (kevin14) foi arquivado em 2022: nao funciona mais.
# Em 2026 a extracao do Facebook exige navegador grafico com Playwright +
# stealth, cookies de sessao validos e comportamento humano randomizado.

_STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
window.chrome = { runtime: {} };
const _get = Object.getPrototypeOf(Intl.DateTimeFormat).format;
Intl.DateTimeFormat.prototype.format = function (...args) {
  return _get.call(this, ...args);
};
"""


class FacebookScraper(BaseScraper):
    """Coleta posts/comentarios do Facebook via Playwright + stealth.

    Autenticacao por cookies.txt do navegador (preferencial) ou login
    username/password (fallback). Busca usa a URL publica de pesquisa de
    posts e rolagem humana randomizada. Melhor esforco: o Facebook ofusca o
    DOM diariamente, entao o parser de `role="article"` pode exigir ajustes.
    """

    plataforma = PLATAFORMA_FACEBOOK

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.cookies_file = cfg.get("cookies_file", "")
        self.usuario = cfg.get("username", "")
        self.senha = cfg.get("password", "")
        self.headless = cfg.get("headless", True)
        self.max_rolagens = cfg.get("max_rolagens", 5)

    def _carregar_cookies(self, arquivo: str) -> list[dict]:
        # Aceita o formato Netscape (cookies.txt) ou JSON (lista de dicts)
        path = Path(arquivo)
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        cookies = []
        for linha in path.read_text(encoding="utf-8").splitlines():
            if linha.startswith("#") or not linha.strip():
                continue
            campos = linha.split("\t")
            if len(campos) >= 7:
                cookies.append(
                    {
                        "name": campos[5],
                        "value": campos[6],
                        "domain": campos[0],
                        "path": campos[2],
                        "secure": campos[3].upper() == "TRUE",
                        "httpOnly": campos[4].upper() == "TRUE",
                    }
                )
        return cookies

    @staticmethod
    def _rolar_humano(page) -> None:
        for _ in range(random.randint(2, 4)):
            page.mouse.wheel(0, random.randint(700, 1400))
            time.sleep(random.uniform(1.2, 3.5))

    def _coletar_pagina(self, page, termo: str, agente_id: str, limite: int) -> list[RawItem]:
        from bs4 import BeautifulSoup

        itens: list[RawItem] = []
        for _ in range(self.max_rolagens):
            self._rolar_humano(page)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            for artigo in soup.find_all(attrs={"role": "article"}):
                texto = artigo.get_text(" ", strip=True)
                if not texto or len(texto) < 10:
                    continue
                link = artigo.find("a", href=True)
                url = link["href"] if link else ""
                itens.append(
                    RawItem(
                        agente_id=agente_id,
                        id_externo=self._hash_id(termo + texto[:120]),
                        plataforma=self.plataforma,
                        tipo=TIPO_POSTAGEM,
                        texto_limpo=texto,
                        data_publicacao=None,
                        autor=termo,
                        url=url,
                        alcance=0,
                        metadados={"veiculo": termo},
                    )
                )
            if len(itens) >= limite:
                break
        return itens

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            logger.error("Facebook: instale o Playwright (pip install playwright && playwright install chromium). %s", e)
            return []

        itens: list[RawItem] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            contexto = browser.new_context(
                locale="pt-BR",
                timezone_id="America/Cuiaba",
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            contexto.add_init_script(_STEALTH_INIT)

            if self.cookies_file and Path(self.cookies_file).exists():
                contexto.add_cookies(self._carregar_cookies(self.cookies_file))
                logger.info("Facebook: cookies injetados de %s", self.cookies_file)
            elif self.usuario and self.senha:
                self._login(contexto)

            pagina = contexto.new_page()
            for termo in agente.get("termos_de_busca", []):
                try:
                    url_busca = f"https://www.facebook.com/search/posts/?q={quote(termo)}"
                    pagina.goto(url_busca, wait_until="domcontentloaded", timeout=45000)
                    self._rolar_humano(pagina)
                    itens.extend(self._coletar_pagina(pagina, termo, agente["id"], limite))
                except Exception as e:  # noqa: BLE001
                    logger.warning("Facebook: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
            contexto.close()
            browser.close()
        logger.info("Facebook: %d itens para %s", len(itens), agente["id"])
        return itens

    def _login(self, contexto) -> None:
        try:
            pagina = contexto.new_page()
            pagina.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=45000)
            pagina.fill("#email", self.usuario)
            pagina.fill("#pass", self.senha)
            self._rolar_humano(pagina)
            pagina.click('button[name="login"]')
            time.sleep(random.uniform(4, 8))
            pagina.close()
            logger.info("Facebook: login efetuado como %s.", self.usuario)
        except Exception as e:  # noqa: BLE001
            logger.error("Facebook: falha no login: %s", e)