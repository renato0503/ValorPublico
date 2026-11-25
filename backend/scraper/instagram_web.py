"""Coletor de posts do Instagram via navegador real (conta propria).

Substitui o caminho antigo do `instaloader` (que era banido por IP em alta
cadencia) por uma sessao de navegador persistente do **proprio dono**, sem
senha no repositorio. Estrategia anti-bot:

  * perfil persistente do Chromium/Patchright criado uma unica vez com
    `--login` (o dono entra na conta dele naquele navegador);
  * a coleta roda dentro da pagina autenticada (`fetch` same-origin), usando
    a API interna do Instagram (`/api/v1/media/<id>/...`) com o cabecalho
    `x-ig-app-id` — nada de cookies de terceiros nem de conta falsa;
  * Patchright (quando disponivel) remove as marcas de automacao do CDP;
  * ritmo humano entre posts, retry com backoff e **parada imediata** ao
    detectar parede de login ou CAPTCHA (nunca resolve desafio).

O que sai daqui espelha a coleta manual (`fotoN.png` + `fotoN.md`), alem de
um `post.json` estruturado pronto para virar `RawItem` da ingestao.
"""

from __future__ import annotations

import io
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from core.logger import get_logger
from scraper.models import PLATAFORMA_INSTAGRAM, TIPO_POSTAGEM

logger = get_logger(__name__)

ALFABETO_SHORTCODE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
IG_APP_ID = "936619743392459"
BASE_URL = "https://www.instagram.com"
PASTA_PERFIL_PADRAO = Path.home() / ".cerra_clipping" / "instagram_perfil"

_JS_FETCH = """
async ({path, app}) => {
  try {
    const r = await fetch(path, {
      headers: {'x-ig-app-id': app, 'accept': '*/*'},
      credentials: 'include',
    });
    const txt = await r.text();
    let json = null;
    try { json = JSON.parse(txt); } catch (e) {}
    return {status: r.status, json, texto: txt.slice(0, 200)};
  } catch (e) {
    return {status: 0, json: null, texto: String(e).slice(0, 200)};
  }
}
"""


class BloqueioInstagram(RuntimeError):
    """Login/CAPTCHA detectado: a coleta para (nunca resolve desafio)."""

    def __init__(self, url: str, tipo: str) -> None:
        super().__init__(f"Bloqueio '{tipo}' em {url}")
        self.url = url
        self.tipo = tipo


# ----------------------------------------------------------------------
# Funcoes puras (testaveis sem rede)
# ----------------------------------------------------------------------
def shortcode_da_url(url: str) -> str | None:
    """Extrai o shortcode de uma URL de post/reel/tv do Instagram."""
    try:
        partes = urlparse(url)
    except Exception:  # noqa: BLE001
        return None
    host = (partes.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in ("instagram.com", "instagr.am"):
        return None
    segmentos = [s for s in partes.path.split("/") if s]
    if len(segmentos) >= 2 and segmentos[0] in ("p", "reel", "tv"):
        return segmentos[1]
    return None


def shortcode_para_media_id(shortcode: str) -> str:
    """Converte o shortcode (base64 url-safe) no id numerico da midia."""
    numero = 0
    for letra in shortcode:
        indice = ALFABETO_SHORTCODE.find(letra)
        if indice < 0:
            raise ValueError(f"shortcode invalido: {shortcode!r}")
        numero = numero * 64 + indice
    return str(numero)


def media_id_para_shortcode(media_id: str | int) -> str:
    """Inverso de `shortcode_para_media_id` (usado nos testes)."""
    numero = int(media_id)
    if numero <= 0:
        return "A"
    saida = ""
    while numero:
        numero, resto = divmod(numero, 64)
        saida = ALFABETO_SHORTCODE[resto] + saida
    return saida


def tipo_de_midia(media_type: int | None) -> str:
    return {1: "Foto", 2: "Video", 8: "Carrossel"}.get(int(media_type or 0), "Desconhecido")


def _maior_candidato(candidatos: list[dict]) -> dict:
    if not candidatos:
        return {}
    return max(
        candidatos,
        key=lambda c: int(c.get("width") or 0) * int(c.get("height") or 0),
    )


def extrair_capa_url(item: dict) -> str:
    """URL da melhor capa (foto, frame de video ou 1o item do carrossel)."""
    alvo = item
    if int(item.get("media_type") or 0) == 8 and item.get("carousel_media"):
        alvo = item["carousel_media"][0]
    candidatos = (alvo.get("image_versions2") or {}).get("candidates") or []
    capa = _maior_candidato(candidatos)
    return capa.get("url", "")


RE_SHORTCODE_HTML = re.compile(r'"shortcode"\s*:\s*"([A-Za-z0-9_-]+)"')


def extrair_shortcodes_html(html: str) -> list[str]:
    """Le os shortcodes direto do HTML da pagina do perfil (sem API extra)."""
    vistos: list[str] = []
    for achado in RE_SHORTCODE_HTML.finditer(html or ""):
        codigo = achado.group(1)
        if codigo not in vistos:
            vistos.append(codigo)
    return vistos


def extrair_imagens(item: dict) -> list[str]:
    """URLs de todas as imagens: capa de video/foto unica ou todo o carrossel."""
    if int(item.get("media_type") or 0) == 8 and item.get("carousel_media"):
        urls: list[str] = []
        for midia in item["carousel_media"]:
            candidatos = (midia.get("image_versions2") or {}).get("candidates") or []
            url = _maior_candidato(candidatos).get("url", "")
            if url:
                urls.append(url)
        return urls
    capa = extrair_capa_url(item)
    return [capa] if capa else []


def _iso(epoch: int | float | None) -> datetime | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _parse_comentario(bruto: dict, shortcode: str, responde_a: str = "") -> dict:
    usuario = bruto.get("user") or {}
    pk = str(bruto.get("pk") or "")
    return {
        "id": pk,
        "autor": usuario.get("username", ""),
        "nome": usuario.get("full_name", ""),
        "texto": (bruto.get("text") or "").strip(),
        "criado_em": _iso(bruto.get("created_at") or bruto.get("created_at_utc")),
        "curtidas": int(bruto.get("comment_like_count") or 0),
        "responde_a": responde_a,
        "permalink": f"{BASE_URL}/p/{shortcode}/c/{pk}/" if pk else f"{BASE_URL}/p/{shortcode}/",
    }


def parse_comentarios(pagina: dict, shortcode: str) -> list[dict]:
    """Normaliza uma pagina de `/comments/` (inclui respostas em preview)."""
    saida: list[dict] = []
    for bruto in pagina.get("comments") or []:
        pai = _parse_comentario(bruto, shortcode)
        saida.append(pai)
        for filho in bruto.get("preview_child_comments") or []:
            saida.append(_parse_comentario(filho, shortcode, responde_a=pai["id"]))
    return saida


def montar_post(
    item: dict,
    comentarios: list[dict],
    coletado_em: datetime | None = None,
) -> dict:
    """Monta o dicionario final de um post a partir do item da API."""
    usuario = item.get("user") or {}
    shortcode = item.get("code") or ""
    caption = item.get("caption") or {}
    legenda = (caption.get("text") or "").strip()
    return {
        "shortcode": shortcode,
        "media_id": str(item.get("pk") or item.get("id") or ""),
        "url": f"{BASE_URL}/p/{shortcode}/",
        "autor": usuario.get("username", ""),
        "autor_nome": usuario.get("full_name", ""),
        "legenda": legenda,
        "data_publicacao": _iso(item.get("taken_at")),
        "curtidas": int(item.get("like_count") or 0),
        "total_comentarios": int(item.get("comment_count") or 0),
        "tipo_midia": tipo_de_midia(item.get("media_type")),
        "capa_url": extrair_capa_url(item),
        "imagens": extrair_imagens(item),
        "comentarios": comentarios,
        "coletado_em": coletado_em or datetime.now(timezone.utc),
        "metadados": {
            "media_type": item.get("media_type"),
            "video": int(item.get("media_type") or 0) == 2,
            "carrossel": int(item.get("media_type") or 0) == 8,
            "localizacao": (item.get("location") or {}).get("name", ""),
            "comentarios_coletados": len(comentarios),
        },
    }


def post_para_raw_item(post: dict, agente_id: str) -> dict:
    """Converte o post no formato `RawItem` usado pela ingestao."""
    return {
        "agente_id": agente_id,
        "id_externo": post.get("shortcode", ""),
        "plataforma": PLATAFORMA_INSTAGRAM,
        "tipo": TIPO_POSTAGEM,
        "texto_limpo": post.get("legenda", ""),
        "data_publicacao": post.get("data_publicacao"),
        "autor": post.get("autor", ""),
        "url": post.get("url", ""),
        "alcance": int(post.get("curtidas") or 0) + int(post.get("total_comentarios") or 0),
        "metadados": {
            "curtidas": post.get("curtidas"),
            "comentarios": post.get("total_comentarios"),
            "tipo_midia": post.get("tipo_midia"),
            "coletado_em": _para_texto(post.get("coletado_em")),
            "origem_coleta": "navegador",
        },
        "midia": [
            {"url_original": post.get("capa_url"), "origem": "api", "ordem": 0}
        ]
        if post.get("capa_url")
        else [],
    }


def _para_texto(valor) -> str:
    if isinstance(valor, datetime):
        return valor.isoformat()
    return valor or ""


def _data_curta(valor) -> str:
    if isinstance(valor, datetime):
        return valor.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "—"


def post_para_markdown(post: dict) -> str:
    """Texto no mesmo espirito da coleta manual (descricao + comentarios)."""
    linhas = [
        f"# {post.get('autor') or 'post'} — {post.get('shortcode')}",
        "",
        f"- URL: {post.get('url')}",
        f"- Publicado em: {_data_curta(post.get('data_publicacao'))}",
        f"- Coletado em: {_data_curta(post.get('coletado_em'))}",
        f"- Tipo: {post.get('tipo_midia')} | Curtidas: {post.get('curtidas')} | "
        f"Comentarios: {post.get('total_comentarios')}",
        "",
        "## Descrição",
        "",
        post.get("legenda") or "(sem legenda)",
        "",
        f"## Comentários ({len(post.get('comentarios') or [])})",
        "",
    ]
    for indice, comentario in enumerate(post.get("comentarios") or [], start=1):
        marca = " ↳" if comentario.get("responde_a") else ""
        linhas.append(
            f"{indice}. **{marca}@{comentario.get('autor') or 'anonimo'}** · "
            f"{_data_curta(comentario.get('criado_em'))} · "
            f"{comentario.get('curtidas', 0)} curtidas"
        )
        linhas.append(f"   {comentario.get('texto') or '(vazio)'}")
        linhas.append(f"   {comentario.get('permalink')}")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def post_para_json(post: dict) -> str:
    return json.dumps(post, ensure_ascii=False, indent=2, default=str)


# ----------------------------------------------------------------------
# Coletor (navegador real + API interna)
# ----------------------------------------------------------------------
class InstagramWebColetor:
    """Coleta posts/comentarios usando o navegador persistente do dono."""

    def __init__(
        self,
        perfil_dir: str | Path | None = None,
        headless: bool = True,
        pausa_min: float = 8.0,
        pausa_max: float = 20.0,
        pausa_posts_min: float = 30.0,
        pausa_posts_max: float = 90.0,
        timeout_ms: int = 30000,
        max_retries: int = 2,
    ) -> None:
        self.perfil_dir = Path(perfil_dir or PASTA_PERFIL_PADRAO)
        self.estado_path = self.perfil_dir.parent / "instagram_estado.json"
        self.headless = headless
        self.pausa_min = pausa_min
        self.pausa_max = pausa_max
        self.pausa_posts_min = pausa_posts_min
        self.pausa_posts_max = pausa_posts_max
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self.motor = ""
        self._pw = None
        self._context = None
        self._browser = None

    def __enter__(self) -> "InstagramWebColetor":
        self.abrir()
        return self

    def __exit__(self, *_) -> None:
        self.fechar()

    def _playwright(self):
        try:
            from patchright.sync_api import sync_playwright

            self.motor = "patchright"
            return sync_playwright
        except Exception:  # noqa: BLE001
            from playwright.sync_api import sync_playwright

            self.motor = "playwright"
            return sync_playwright

    def abrir(self, headless: bool | None = None) -> None:
        self.perfil_dir.mkdir(parents=True, exist_ok=True)
        motor = self._playwright()
        self._pw = motor().start()
        alvo_headless = self.headless if headless is None else headless
        opcoes: dict = {
            "locale": "pt-BR",
            "timezone_id": "America/Cuiaba",
            "viewport": {"width": 1280, "height": 1000},
        }
        if self.estado_path.exists():
            self._browser = self._pw.chromium.launch(
                headless=alvo_headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            opcoes["storage_state"] = str(self.estado_path)
            self._context = self._browser.new_context(**opcoes)
            logger.info("Instagram: contexto unico com a sessao salva (%s).", self.motor)
            return
        self._context = self._pw.chromium.launch_persistent_context(
            str(self.perfil_dir),
            headless=alvo_headless,
            args=["--disable-blink-features=AutomationControlled"],
            **opcoes,
        )
        logger.info("Instagram: perfil persistente aberto (%s).", self.motor)

    def _restaurar_estado(self) -> None:
        """Reinjeta os cookies salvos (sobrevive a fechar/abrir e a headless)."""
        if self._context is None or not self.estado_path.exists():
            return
        try:
            estado = json.loads(self.estado_path.read_text(encoding="utf-8"))
            cookies = estado.get("cookies") or []
            if cookies:
                self._context.add_cookies(cookies)
                logger.info("Instagram: %d cookies restaurados de %s.", len(cookies), self.estado_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Nao foi possivel restaurar a sessao: %s", str(exc)[:100])

    def salvar_estado(self) -> None:
        """Grava cookies/localStorage em JSON (sem senha; so a sessao)."""
        if self._context is None:
            return
        try:
            self.estado_path.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(self.estado_path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao salvar a sessao: %s", str(exc)[:100])

    def fechar(self) -> None:
        self.salvar_estado()
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
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = None
        self._browser = None
        self._pw = None

    def _pagina(self):
        if self._context is None:
            raise RuntimeError("Sessao fechada; chame abrir() antes.")
        paginas = self._context.pages
        return paginas[0] if paginas else self._context.new_page()

    def _pausa(self) -> None:
        time.sleep(random.uniform(self.pausa_min, self.pausa_max))

    def _pausa_posts(self) -> None:
        time.sleep(random.uniform(self.pausa_posts_min, self.pausa_posts_max))

    def _comportamento_humano(self, page) -> None:
        """Chega, 'le', mexe o mouse e rola um pouco antes de ler os dados."""
        page.wait_for_timeout(random.randint(2500, 6000))
        try:
            tamanho = page.viewport_size or {"width": 1280, "height": 900}
            largura, altura = tamanho["width"], tamanho["height"]
            x = random.randint(largura // 3, 2 * largura // 3)
            y = random.randint(altura // 3, 2 * altura // 3)
            page.mouse.move(x, y)
            for _ in range(random.randint(3, 6)):
                x = min(largura - 2, max(2, x + random.randint(-60, 60)))
                y = min(altura - 2, max(2, y + random.randint(-50, 50)))
                page.mouse.move(x, y, steps=random.randint(6, 18))
                page.wait_for_timeout(random.randint(150, 500))
            page.mouse.wheel(0, random.randint(120, 380))
            page.wait_for_timeout(random.randint(1200, 3000))
        except Exception:  # noqa: BLE001
            pass

    def _verificar_login(self, page) -> None:
        url = page.url or ""
        if "/accounts/login" in url or "/challenge" in url:
            raise BloqueioInstagram(url, "login")
        try:
            if page.query_selector('input[name="username"]'):
                raise BloqueioInstagram(url, "login")
        except BloqueioInstagram:
            raise
        except Exception:  # noqa: BLE001
            pass

    def _api(self, page, caminho: str) -> dict:
        ultimo = ""
        for tentativa in range(1, self.max_retries + 1):
            resultado = page.evaluate(
                _JS_FETCH, {"path": caminho, "app": IG_APP_ID}
            )
            status = int(resultado.get("status") or 0)
            dados = resultado.get("json")
            texto = (resultado.get("texto") or "").lstrip().lower()
            if status in (401, 403) or (
                isinstance(dados, dict)
                and (dados.get("require_login") or dados.get("message") == "login_required")
            ):
                raise BloqueioInstagram(page.url, "login_api")
            if dados is None and texto.startswith(("<!doctype", "<html")):
                raise BloqueioInstagram(page.url, "login_api")
            if status == 429:
                ultimo = "429 rate limit"
                time.sleep(5 * tentativa)
                continue
            if status == 200 and isinstance(dados, (dict, list)):
                return dados
            ultimo = f"HTTP {status}: {resultado.get('texto', '')[:120]}"
            time.sleep(2 * tentativa)
        raise RuntimeError(f"API do Instagram falhou: {ultimo}")

    def _api_comentarios(
        self, page, media_id: str, shortcode: str, max_comentarios: int, max_paginas: int
    ) -> list[dict]:
        comentarios: list[dict] = []
        min_id = ""
        time.sleep(random.uniform(1.5, 4.0))
        for pagina in range(max_paginas):
            caminho = (
                f"/api/v1/media/{media_id}/comments/"
                "?can_support_threading=true&permalink_enabled=false"
            )
            if min_id:
                caminho += f"&min_id={min_id}"
            dados = self._api(page, caminho)
            novos = parse_comentarios(dados, shortcode)
            comentarios.extend(novos)
            if len(comentarios) >= max_comentarios:
                break
            if not dados.get("has_more_comments") or not dados.get("next_min_id"):
                break
            min_id = str(dados.get("next_min_id"))
            time.sleep(random.uniform(self.pausa_min, self.pausa_max))
        return comentarios[:max_comentarios]

    def coletar_post(
        self,
        url_ou_shortcode: str,
        max_comentarios: int = 300,
        max_paginas: int = 12,
        com_screenshot: bool = True,
    ) -> dict:
        shortcode = shortcode_da_url(url_ou_shortcode) or url_ou_shortcode.strip().strip("/")
        media_id = shortcode_para_media_id(shortcode)
        page = self._pagina()
        page.goto(
            f"{BASE_URL}/p/{shortcode}/",
            wait_until="domcontentloaded",
            timeout=self.timeout_ms,
        )
        if "/challenge" in (page.url or ""):
            raise BloqueioInstagram(page.url, "challenge")
        self._comportamento_humano(page)

        info = self._api(page, f"/api/v1/media/{media_id}/info/")
        itens = info.get("items") or []
        if not itens:
            raise RuntimeError(f"Post {shortcode} sem dados (items vazio).")
        item = itens[0]
        try:
            comentarios = self._api_comentarios(
                page, media_id, shortcode, max_comentarios, max_paginas
            )
        except BloqueioInstagram as exc:
            logger.warning(
                "Comentarios de %s indisponiveis (%s); salvando sem comentarios.",
                shortcode,
                exc.tipo,
            )
            comentarios = []
        post = montar_post(item, comentarios)
        post["screenshot_png"] = self._screenshot(page) if com_screenshot else b""
        return post

    def _screenshot(self, page) -> bytes:
        for seletor in ('article', 'div[role="dialog"] article', 'video', 'img[style*="object-fit"]'):
            try:
                alvo = page.locator(seletor).first
                if alvo.count() and alvo.is_visible():
                    return alvo.screenshot(type="png")
            except Exception:  # noqa: BLE001
                continue
        try:
            return page.screenshot(type="png")
        except Exception:  # noqa: BLE001
            return b""

    def _shortcodes_na_pagina(self, page) -> list[str]:
        """Le os links de posts direto da grade ja renderizada (sem API)."""
        try:
            page.wait_for_selector('a[href*="/p/"], a[href*="/reel/"]', timeout=8000)
        except Exception:  # noqa: BLE001
            return []
        hrefs = page.eval_on_selector_all(
            'a[href*="/p/"], a[href*="/reel/"]',
            'els => els.map(e => e.getAttribute("href"))',
        )
        codigos: list[str] = []
        for href in hrefs:
            url = href if (href or "").startswith("http") else f"{BASE_URL}{href or ''}"
            codigo = shortcode_da_url(url)
            if codigo and codigo not in codigos:
                codigos.append(codigo)
        return codigos

    def coletar_perfil(
        self,
        usuario: str,
        limite: int = 5,
        max_comentarios: int = 300,
        max_paginas: int = 12,
        pular: set[str] | None = None,
    ) -> list[dict]:
        usuario = usuario.strip().lstrip("@")
        pular = {codigo.strip() for codigo in (pular or set()) if codigo.strip()}
        page = self._pagina()
        page.goto(f"{BASE_URL}/{usuario}/", wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._verificar_login(page)
        self._comportamento_humano(page)
        shortcodes = self._shortcodes_na_pagina(page)
        if not shortcodes:
            try:
                dados = self._api(page, f"/api/v1/users/web_profile_info/?username={usuario}")
                bordas = dados["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
                shortcodes = [
                    b["node"]["shortcode"] for b in bordas if b.get("node", {}).get("shortcode")
                ]
            except Exception as exc:  # noqa: BLE001
                logger.info("API do perfil indisponivel: %s", str(exc)[:80])
        shortcodes = [codigo for codigo in shortcodes if codigo not in pular]
        if not shortcodes:
            raise RuntimeError(f"Perfil @{usuario} nao retornou publicacoes.")
        posts: list[dict] = []
        for shortcode in shortcodes[:limite]:
            self._pausa_posts()
            posts.append(
                self.coletar_post(
                    shortcode, max_comentarios=max_comentarios, max_paginas=max_paginas
                )
            )
        return posts

    # ------------------------------------------------------------------
    # Login unico (interativo, perfil persistente)
    # ------------------------------------------------------------------
    def login_interativo(self, espera_segundos: int = 600, usuario_teste: str = "instagram") -> None:
        """Abre o navegador visivel e espera o dono entrar na conta dele."""
        self.abrir(headless=False)
        page = self._pagina()
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded", timeout=self.timeout_ms)
        print(
            "\n=== LOGIN DO INSTAGRAM ===\n"
            "1) Entre na SUA conta no navegador que acabou de abrir.\n"
            "2) Conclua 2FA/challenge se aparecer.\n"
            "3) Volte aqui: o script detecta sozinho quando a sessao estiver pronta.\n"
            f"   (tempo maximo: {espera_segundos}s)\n"
        )
        limite = time.time() + espera_segundos
        ciclos = 0
        while time.time() < limite:
            page.wait_for_timeout(5000)
            self.salvar_estado()
            ciclos += 1
            try:
                if page.query_selector('input[name="username"]'):
                    continue
                if "/accounts/login" in (page.url or "") or "/challenge" in (page.url or ""):
                    continue
                if ciclos % 3:
                    continue
                teste = self._api(
                    page, f"/api/v1/users/web_profile_info/?username={usuario_teste}"
                )
                if teste.get("data", {}).get("user"):
                    self.salvar_estado()
                    print(
                        "Login confirmado. Sessao salva em:",
                        self.estado_path,
                    )
                    return
            except BloqueioInstagram:
                continue
            except Exception:  # noqa: BLE001
                continue
        self.salvar_estado()
        raise RuntimeError("Login nao confirmado dentro do tempo; tente novamente.")

    def baixar_imagem(self, url: str, destino_png: Path) -> Path | None:
        """Baixa uma imagem e grava em PNG (Pillow) — ou no formato original."""
        if not url or self._context is None:
            return None
        try:
            resposta = self._context.request.get(url, timeout=self.timeout_ms)
            if not resposta.ok:
                logger.warning("Imagem indisponivel (%s): %s", resposta.status, url[:80])
                return None
            return gravar_png(resposta.body(), destino_png)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao baixar imagem %s: %s", url[:80], str(exc)[:80])
            return None

    def baixar_capa(self, post: dict, destino_png: Path) -> Path | None:
        """Baixa a capa do post."""
        return self.baixar_imagem(post.get("capa_url") or "", destino_png)


def gravar_png(bytes_imagem: bytes, destino_png: Path) -> Path:
    """Grava bytes de imagem como PNG (converte com Pillow quando possivel)."""
    destino_png.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(bytes_imagem)) as img:
            img.convert("RGB").save(destino_png, format="PNG")
        return destino_png
    except Exception:  # noqa: BLE001
        alternativo = destino_png.with_suffix(".jpg")
        alternativo.write_bytes(bytes_imagem)
        return alternativo


def gravar_post(post: dict, pasta: Path, com_screenshot: bool = True) -> dict:
    """Grava post.json, post.md, descricao.md, comentarios.md e pagina.png."""
    pasta.mkdir(parents=True, exist_ok=True)
    screenshot = post.pop("screenshot_png", b"")
    (pasta / "post.json").write_text(post_para_json(post), encoding="utf-8")
    (pasta / "post.md").write_text(post_para_markdown(post), encoding="utf-8")
    (pasta / "descricao.md").write_text(
        (post.get("legenda") or "") + "\n", encoding="utf-8"
    )
    comentarios_md = "\n".join(
        f"- @{c.get('autor') or 'anonimo'} ({_data_curta(c.get('criado_em'))}): "
        f"{c.get('texto') or ''}  \n  {c.get('permalink')}"
        for c in post.get("comentarios") or []
    )
    (pasta / "comentarios.md").write_text(comentarios_md + "\n", encoding="utf-8")
    if com_screenshot and screenshot:
        (pasta / "pagina.png").write_bytes(screenshot)
    return post


def carregar_post_json(caminho: Path) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))
