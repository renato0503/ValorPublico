"""Evidencia de coleta: print com data, PDF e sha256 (N3/N4 do plano 19).

Serve para:
  - provar o que saiu no dia da coleta (matéria editada/apagada depois);
  - servir de origem de imagem quando a página não tem `og:image` (N3).

O arquivo original **nao** e guardado: fica so o print (1280 px) e o PDF, com o
hash da pagina no momento da coleta.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.scraper.navegador import SessaoNavegador

logger = get_logger(__name__)

LARGURA = 1280


def sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(65536), b""):
            digest.update(bloco)
    return digest.hexdigest()


def capturar(
    url: str,
    pasta: Path,
    nome: str,
    sessao: SessaoNavegador,
    agente_id: str | None = None,
    com_pdf: bool = True,
) -> dict:
    """Captura o print (e o PDF) da pagina.

    Devolve {"ok", "screenshot", "pdf", "sha256", "titulo", "coletado_em", "motivo"}.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    saida = {
        "ok": False,
        "screenshot": "",
        "pdf": "",
        "sha256": "",
        "titulo": "",
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "motivo": "",
    }
    try:
        page = sessao.abrir_pagina(url, agente_id=agente_id)
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"erro:{str(exc)[:120]}"
        return saida
    try:
        saida["titulo"] = page.title()
        destino = pasta / f"{nome}.png"
        page.screenshot(path=str(destino), full_page=False)
        saida["screenshot"] = str(destino)
        if com_pdf:
            destino_pdf = pasta / f"{nome}.pdf"
            page.pdf(path=str(destino_pdf), format="A4", print_background=True)
            saida["pdf"] = str(destino_pdf)
        saida["sha256"] = sha256_arquivo(destino)
        saida["ok"] = True
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"erro:{str(exc)[:120]}"
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001
            pass
    return saida
