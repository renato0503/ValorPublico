"""Logger do nucleo compartilhado (mesma interface dos apps)."""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURADO = False


def get_logger(nome: str) -> logging.Logger:
    global _CONFIGURADO
    if not _CONFIGURADO:
        nivel = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, nivel, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            stream=sys.stdout,
        )
        _CONFIGURADO = True
    return logging.getLogger(nome)
