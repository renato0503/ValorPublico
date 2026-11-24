"""Executor de receitas de coleta (N1/N3 do plano 19).

Uma receita e um roteiro deterministico de navegacao (em JSON, versionado no
git e revisado por humano) que substitui a leitura fragile de HTML:

```json
{"fonte": "camara-cuiaba-pauta", "url": "https://...",
 "passos": [{"acao": "goto"},
            {"acao": "click", "seletor": "text=Pauta da Sessão"},
            {"acao": "extrair", "lista": "table tr",
             "campos": {"titulo": "td:nth-child(2)", "data": "td:nth-child(1)"}}],
 "gerada_por": "stagehand+qwen3:8b", "validada_em": "2026-11-24", "status": "ok"}
```

Acoes suportadas: `goto`, `clicar`, `esperar`, `extrair` (lista de campos),
`rolar` (scroll), `texto` (texto da pagina) e `screenshot`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.scraper.navegador import BloqueioDetectado, SessaoNavegador

logger = get_logger(__name__)

PASTA_RECEITAS = Path("coletores") / "receitas"


def carregar_receitas(pasta: Path | None = None) -> list[dict]:
    """Le todas as receitas de uma pasta (JSON)."""
    pasta = pasta or PASTA_RECEITAS
    receitas: list[dict] = []
    if not pasta.exists():
        return receitas
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            receita = json.loads(arquivo.read_text(encoding="utf-8"))
            receita.setdefault("fonte", arquivo.stem)
            receitas.append(receita)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Receita invalida %s: %s", arquivo.name, exc)
    return receitas


def salvar_receita(receita: dict, pasta: Path | None = None) -> Path:
    """Grava a receita no git (para revisao humana)."""
    pasta = pasta or PASTA_RECEITAS
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{receita['fonte']}.json"
    destino.write_text(json.dumps(receita, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def _extrair(page, passo: dict) -> list[dict]:
    """Executa a acao `extrair`: lista de linhas com os campos pedidos."""
    seletor_lista = passo.get("lista", "tr")
    campos = passo.get("campos", {})
    linhas = []
    for elemento in page.query_selector_all(seletor_lista):
        item = {}
        for nome, seletor in campos.items():
            try:
                alvo = elemento.query_selector(seletor)
            except Exception:  # noqa: BLE001
                alvo = None
            item[nome] = (alvo.inner_text().strip() if alvo else "")
        if any(v for v in item.values()):
            linhas.append(item)
    return linhas


def executar(receita: dict, sessao: SessaoNavegador, agente_id: str | None = None) -> dict:
    """Executa a receita e devolve {"ok", "itens", "evidencia", "motivo"}."""
    saida = {
        "ok": False,
        "itens": [],
        "evidencia": {},
        "motivo": "",
        "fonte": receita.get("fonte", ""),
        "executado_em": datetime.now(timezone.utc).isoformat(),
    }
    url = receita.get("url", "")
    if not url:
        saida["motivo"] = "receita sem url"
        return saida
    try:
        page = sessao.abrir_pagina(url, agente_id=agente_id)
    except BloqueioDetectado as exc:
        saida["motivo"] = f"bloqueio:{exc.tipo}"
        return saida
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"erro:{str(exc)[:120]}"
        return saida

    try:
        for passo in receita.get("passos", []):
            acao = passo.get("acao")
            if acao == "goto":
                alvo = passo.get("url") or url
                if alvo != url:
                    page.goto(alvo, wait_until="domcontentloaded", timeout=sessao.timeout_ms)
            elif acao == "clicar":
                seletor = passo.get("seletor", "")
                if seletor.startswith("text="):
                    page.get_by_text(seletor[5:], exact=False).first.click(timeout=8000)
                else:
                    page.click(seletor, timeout=8000)
                page.wait_for_timeout(passo.get("espera_ms", 1200))
            elif acao == "esperar":
                page.wait_for_timeout(int(passo.get("ms", 1000)))
            elif acao == "rolar":
                page.mouse.wheel(0, int(passo.get("px", 800)))
                page.wait_for_timeout(500)
            elif acao == "extrair":
                saida["itens"] = _extrair(page, passo)
            elif acao == "texto":
                saida["texto"] = page.inner_text("body")[:20000]
            elif acao == "screenshot":
                saida["evidencia"]["html_sha"] = ""
        saida["ok"] = bool(saida["itens"] or saida.get("texto"))
        if not saida["ok"]:
            saida["motivo"] = "sem_resultado"
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"erro:{str(exc)[:160]}"
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001
            pass
    return saida


def status_receitas(receitas: list[dict]) -> dict:
    """Resumo do estado das receitas (para o painel / CI)."""
    por_status: dict[str, int] = {}
    for receita in receitas:
        status = (receita.get("status") or "desconhecido").lower()
        por_status[status] = por_status.get(status, 0) + 1
    return {
        "total": len(receitas),
        "por_status": por_status,
        "fontes": [r.get("fonte", "") for r in receitas],
    }


RE_URL = re.compile(r"^https?://", re.IGNORECASE)


def url_valida(url: str) -> bool:
    """Guarda anti-SSRF basica: so http(s) publicos."""
    if not url or not RE_URL.match(url):
        return False
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return False
    if host.startswith(("10.", "192.168.", "169.254.")):
        return False
    return True
