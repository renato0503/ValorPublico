"""Tipo e tier dos veículos que publicam sobre o Governo de MT (plano 22).

Lista editável: ``data/seeds/veiculos_mt.json``.
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seeds" / "veiculos_mt.json"

CANAIS = {
    "tier1": "Grandes portais e jornais",
    "tier2": "Portais regionais",
    "tier3": "Outros sites e blogs",
    "governo": "Sites do próprio Governo",
    "instituicoes": "Outras instituições",
    "redes": "Redes sociais (busca)",
}


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(base.lower().split())


@lru_cache(maxsize=1)
def _dados() -> dict:
    d = json.loads(SEED.read_text(encoding="utf-8"))
    return {
        "tier1": {_norm(v) for v in d.get("tier1", [])},
        "tier2": {_norm(v) for v in d.get("tier2", [])},
        "governo": [_norm(v) for v in d.get("sites_do_governo_contem", [])],
        "instituicoes": [_norm(v) for v in d.get("outras_instituicoes_contem", [])],
        "redes": [_norm(v) for v in d.get("redes_contem", [])],
    }


def classificar(veiculo: str) -> dict:
    """{"tipo": imprensa|governo|instituicoes|redes, "tier": "Tier 1|2|3"|"", "canal": rótulo}."""
    v = _norm(veiculo)
    d = _dados()
    if any(t in v for t in d["redes"]):
        return {"tipo": "redes", "tier": "", "canal": CANAIS["redes"]}
    if any(t in v for t in d["governo"]):
        return {"tipo": "governo", "tier": "", "canal": CANAIS["governo"]}
    if v in d["tier1"]:
        return {"tipo": "imprensa", "tier": "Tier 1", "canal": CANAIS["tier1"]}
    if v in d["tier2"]:
        return {"tipo": "imprensa", "tier": "Tier 2", "canal": CANAIS["tier2"]}
    if any(t in v for t in d["instituicoes"]):
        return {"tipo": "instituicoes", "tier": "", "canal": CANAIS["instituicoes"]}
    return {"tipo": "imprensa", "tier": "Tier 3", "canal": CANAIS["tier3"]}
