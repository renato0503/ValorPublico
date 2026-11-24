"""Fonte unica dos quatro orgaos (frentes) do ValorPublico.

O ValorPublico e vendido para o ORGAO. Hoje temos quatro frentes:

    cuiaba          Camara Municipal de Cuiaba
    varzea-grande   Camara Municipal de Varzea Grande
    almt            Assembleia Legislativa de Mato Grosso
    governo-mt      Governo do Estado de Mato Grosso

A separacao e total: cada agregado gravado no Firestore carrega o campo
``orgao`` e as ``firestore.rules`` so deixam o usuario ler o orgao dele.

IDs canonicos (usados nas colecoes):

    orgao          cidade (campo `cidade`)        doc metricas_por_cidade
    -----------    ----------------------------   -------------------------
    cuiaba         Cuiaba                         cuiaba
    varzea-grande  Varzea Grande                  varzea-grande
    almt           Mato Grosso                    mato-grosso
    governo-mt     Governo de Mato Grosso         governo-de-mato-grosso

    orgao          casa (campo `casa`)            doc metricas_por_casa
    -----------    ----------------------------   -------------------------
    cuiaba         Camara Cuiaba                  camara-cuiaba
    varzea-grande  Camara VG                      camara-vg
    almt           ALMT                           almt
    governo-mt     Governo MT                     governo-mt

Este modulo e espelhado em ``frontend/js/orgaos.js``. Ao mudar um id, mude
nos dois lugares e rode ``scripts/carimbar_orgao.py``.
"""

from __future__ import annotations

import re
import unicodedata

ORGAOS: dict[str, dict] = {
    "cuiaba": {
        "slug": "cuiaba",
        "rotulo": "Camara Municipal de Cuiaba",
        "cidade": "Cuiaba",
        "cidade_doc": "cuiaba",
        "casa": "Camara Cuiaba",
        "casa_doc": "camara-cuiaba",
    },
    "varzea-grande": {
        "slug": "varzea-grande",
        "rotulo": "Camara Municipal de Varzea Grande",
        "cidade": "Varzea Grande",
        "cidade_doc": "varzea-grande",
        "casa": "Camara VG",
        "casa_doc": "camara-vg",
    },
    "almt": {
        "slug": "almt",
        "rotulo": "Assembleia Legislativa de Mato Grosso",
        "cidade": "Mato Grosso",
        "cidade_doc": "mato-grosso",
        "casa": "ALMT",
        "casa_doc": "almt",
    },
    "governo-mt": {
        "slug": "governo-mt",
        "rotulo": "Governo do Estado de Mato Grosso",
        "cidade": "Governo de Mato Grosso",
        "cidade_doc": "governo-de-mato-grosso",
        "casa": "Governo MT",
        "casa_doc": "governo-mt",
    },
}

# Agentes do Executivo que nao estao no roster de parlamentares.
AGENTES_GOVERNO = {
    "governo-mt",
    "governador-otaviano-pivetta",
    "interino-max-russi",
    "max-russi",
}


def _norm(texto: object) -> str:
    """Minusculas sem acento, para comparar cidade/casa de forma tolerante."""
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return re.sub(r"\s+", " ", base.encode("ascii", "ignore").decode().strip().lower())


POR_CIDADE = {_norm(v["cidade"]): slug for slug, v in ORGAOS.items()}
POR_CASA = {_norm(v["casa"]): slug for slug, v in ORGAOS.items()}
POR_CIDADE_DOC = {v["cidade_doc"]: slug for slug, v in ORGAOS.items()}
POR_CASA_DOC = {v["casa_doc"]: slug for slug, v in ORGAOS.items()}


def slugify(texto: object) -> str:
    base = unicodedata.normalize("NFKD", str(texto or ""))
    base = base.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def orgao_da_cidade(cidade: object) -> str:
    return POR_CIDADE.get(_norm(cidade), "")


def orgao_da_casa(casa: object) -> str:
    return POR_CASA.get(_norm(casa), "")


def orgao_do_agente(agente: dict | None) -> str:
    """Orgao de um documento de `agentes_publicos` (usa `casa` e cai em `cidade`)."""
    if not isinstance(agente, dict):
        return ""
    casa = agente.get("casa") or ""
    if casa:
        slug = orgao_da_casa(casa)
        if slug:
            return slug
    return orgao_da_cidade(agente.get("cidade"))


def orgao_do_escopo(chave: object) -> str:
    """Orgao de um escopo `cidade-<doc>` / `casa-<doc>` (agente exige lookup)."""
    texto = str(chave or "")
    if texto.startswith("cidade-"):
        return POR_CIDADE_DOC.get(texto[len("cidade-") :], "")
    if texto.startswith("casa-"):
        return POR_CASA_DOC.get(texto[len("casa-") :], "")
    return ""


def info(slug: object) -> dict:
    return ORGAOS.get(str(slug or ""), {})
