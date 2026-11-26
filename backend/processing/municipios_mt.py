"""Municípios de Mato Grosso citados numa notícia (plano 22: "por município").

Lista oficial: ``data/seeds/municipios_mt.json`` (IBGE, 142 municípios).

Regras:
* comparação sem acento e sem apóstrofo ("Mirassol d'Oeste" = "mirassol doeste");
* nomes mais longos primeiro, e o trecho casado é "consumido" (assim
  "Lucas do Rio Verde" não vira também outro município);
* nomes ambíguos (palavras comuns, nomes de pessoa ou de cidades de outros
  estados) só contam com maiúscula e contexto de lugar: preposição antes
  ("em Sorriso", "de Cláudia") ou "MT" depois ("Sorriso-MT", "Sorriso (MT)").
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seeds" / "municipios_mt.json"

# Nomes que também são palavras/nomes de pessoa ou existem em outros estados.
AMBIGUOS = {
    "sorriso", "claudia", "denise", "vera", "feliz natal", "novo mundo", "agua boa",
    "tesouro", "jangada", "nobres", "rio branco", "nova brasilandia", "santa terezinha",
    "vila rica", "juara", "planalto da serra", "uniao do sul", "general carneiro",
    "santo afonso", "colider", "carlinda", "luciara", "itauba", "matupa",
    "porto estrela", "castanheira", "comodoro", "cocalinho", "querencia",
}
_PREPOSICOES = r"(?:em|de|do|da|no|na|para|pra|a|ate|entre|e|por|pelo|pela)"
_SUFIXO_MT = r"\s*(?:[-/(]\s*MT\b|\bMT\b)"


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")


def _preparar(texto: str) -> str:
    """Sem acento, sem apóstrofo, mantendo maiúsculas (para os ambíguos)."""
    t = _sem_acento(texto).replace("'", "").replace("’", "").replace("´", "")
    return re.sub(r"\s+", " ", t)


@lru_cache(maxsize=1)
def municipios() -> list[dict]:
    dados = json.loads(SEED.read_text(encoding="utf-8"))
    return dados["municipios"]


@lru_cache(maxsize=1)
def _padroes() -> list[tuple[dict, re.Pattern, bool]]:
    saida = []
    for m in sorted(municipios(), key=lambda x: -len(x["nome"])):
        base = _preparar(m["nome"])
        chave = base.lower()
        ambiguo = chave in AMBIGUOS
        corpo = r"\s+".join(re.escape(p) for p in base.split())
        if ambiguo:
            # nome com maiúscula obrigatória + contexto de lugar; a preposição
            # pode vir em maiúscula no início da frase
            padrao = re.compile(
                rf"(?:(?<![A-Za-z0-9])(?i:{_PREPOSICOES})\s+{corpo}(?![A-Za-z0-9])"
                rf"|(?<![A-Za-z0-9]){corpo}(?={_SUFIXO_MT}))"
            )
        else:
            padrao = re.compile(rf"(?<![A-Za-z0-9]){corpo}(?![A-Za-z0-9])", re.IGNORECASE)
        saida.append((m, padrao, ambiguo))
    return saida


def detectar(texto: str) -> list[str]:
    """Nomes oficiais dos municípios de MT citados no texto (sem repetição)."""
    t = _preparar(texto)
    achados: list[str] = []
    for m, padrao, _ in _padroes():
        casou = padrao.search(t)
        if not casou:
            continue
        achados.append(m["nome"])
        # consome o trecho para não casar um nome contido em outro
        ini, fim = casou.span()
        t = t[:ini] + " " * (fim - ini) + t[fim:]
    return sorted(achados)


def por_nome() -> dict[str, dict]:
    return {m["nome"]: m for m in municipios()}
