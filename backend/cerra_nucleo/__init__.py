"""Nucleo compartilhado dos dois apps (AssessorPublico e ValorPublico).

Decisao D1-D11 do plano 15: **D6 = nucleo unico**.
Este pacote e a fonte canonica do codigo que NAO depende do produto
(assessor x valor). Ele e instalado/vendored nos dois repositorios para que o
CI do GitHub Actions continue funcionando, e a copia e conferida por
`sync_nucleo.py` + `tests/teste_nucleo.py` (guarda de deriva).

Regra do dono: nada de API paga. Todo modulo aqui usa fonte oficial e
gratuita ou roda localmente (R, Ollama).
"""

from __future__ import annotations

VERSION = "0.1.0"
TAG = "v0.1.0"

__all__ = ["VERSION", "TAG"]
