"""Carimba o campo `orgao` em todo o acervo (separacao total das 4 frentes).

O ValorPublico e vendido para o ORGAO e a separacao e feita pelas
`firestore.rules`: o usuario so le documentos cujo `orgao` e o dele. Os
documentos que ja existiam antes dessa regra nao tinham o campo, entao este
script os atualiza (idempotente, lote de 400, `merge=True`).

Orgaos: cuiaba | varzea-grande | almt | governo-mt (ver `core/orgaos.py`).

Uso (a partir de `backend/`):
    python scripts/carimbar_orgao.py --dry-run
    python scripts/carimbar_orgao.py
    python scripts/carimbar_orgao.py --colecoes radares,alertas,cobertura
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger  # noqa: E402
from core.orgaos import (  # noqa: E402
    AGENTES_GOVERNO,
    ORGAOS,
    POR_CASA_DOC,
    POR_CIDADE_DOC,
    orgao_da_cidade,
    orgao_do_agente,
)

logger = get_logger(__name__)

LOTE = 400

COLLECTION_ORG = "orgao"
COLLECTIONS = [
    "agentes_publicos",
    "metricas_por_cidade",
    "metricas_por_casa",
    "metricas_por_agente",
    "metricas_por_secretaria",
    "radares",
    "alertas",
    "cobertura",
    "newsletters",
    "analise_lexical",
    "releases_ia",
    "relatorio_semanal",
    "discurso_semanal",
    "simulacao_semanal",
    "personas",
    "demandas",
]


def _agentes(db) -> dict[str, str]:
    """Mapa id do agente -> orgao (fonte: casa/cidade do roster)."""
    mapa: dict[str, str] = {}
    for doc in db.collection("agentes_publicos").stream():
        mapa[doc.id] = orgao_do_agente(doc.to_dict() or {})
    return mapa


def _pela_chave(chave: str, agentes: dict[str, str]) -> str:
    chave = str(chave or "")
    if chave.startswith("cidade-"):
        return POR_CIDADE_DOC.get(chave[len("cidade-") :], "")
    if chave.startswith("casa-"):
        return POR_CASA_DOC.get(chave[len("casa-") :], "")
    if chave.startswith("agente-"):
        return agentes.get(chave[len("agente-") :], "")
    if chave in POR_CIDADE_DOC:
        return POR_CIDADE_DOC[chave]
    if chave in AGENTES_GOVERNO:
        return "governo-mt"
    return agentes.get(chave, "")


def resolver(colecao: str, doc_id: str, dados: dict, agentes: dict[str, str]) -> str:
    """Descobre o orgao de um documento existente."""
    # 1) ja carimbado (e valido)
    atual = dados.get("orgao")
    if atual in ORGAOS:
        return atual

    # 2) colecoes de agregado por id de documento
    if colecao == "metricas_por_cidade":
        return POR_CIDADE_DOC.get(doc_id, "")
    if colecao == "metricas_por_casa":
        return POR_CASA_DOC.get(doc_id, "")
    if colecao == "metricas_por_secretaria":
        return "governo-mt"
    if colecao == "metricas":
        return ""

    # 3) agentes (roster e metricas por agente)
    if colecao == "agentes_publicos":
        return orgao_do_agente(dados)
    if colecao == "metricas_por_agente":
        if doc_id in AGENTES_GOVERNO:
            return "governo-mt"
        return agentes.get(doc_id, "")

    # 4) colecoes por escopo (docId = chave do escopo)
    chave = _pela_chave(doc_id, agentes)
    if chave:
        return chave

    # 5) escopo dentro do documento
    escopo = dados.get("escopo")
    if isinstance(escopo, dict):
        tipo = escopo.get("tipo") or ""
        meta = escopo.get("chave") or ""
        if tipo == "cidade":
            return POR_CIDADE_DOC.get(str(meta), "") or orgao_da_cidade(meta)
        if tipo == "agente":
            return agentes.get(str(meta), "")
    if isinstance(escopo, str):
        chave = _pela_chave(escopo, agentes)
        if chave:
            return chave

    # 6) ids compostos `escopo__semana`
    if "__" in doc_id:
        base = doc_id.split("__", 1)[0]
        chave = _pela_chave(base, agentes)
        if chave:
            return chave
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Carimba o orgao nos documentos.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--colecoes",
        default="",
        help="Lista separada por virgula (padrao: todas).",
    )
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    agentes = _agentes(db)
    logger.info("Roster carregado: %d agentes.", len(agentes))

    escolhidas = (
        [c.strip() for c in args.colecoes.split(",") if c.strip()]
        if args.colecoes
        else COLLECTIONS
    )

    total_por_orgao: Counter = Counter()
    total_alterados = 0
    lote = db.batch()
    pendentes = 0

    for colecao in escolhidas:
        alterados = 0
        vistos = 0
        for doc in db.collection(colecao).stream():
            vistos += 1
            dados = doc.to_dict() or {}
            orgao = resolver(colecao, doc.id, dados, agentes)
            if not orgao:
                continue
            if dados.get("orgao") == orgao:
                continue
            alterados += 1
            total_alterados += 1
            total_por_orgao[orgao] += 1
            if not args.dry_run:
                lote.set(
                    db.collection(colecao).document(doc.id),
                    {COLLECTION_ORG: orgao},
                    merge=True,
                )
                pendentes += 1
                if pendentes >= LOTE:
                    lote.commit()
                    lote = db.batch()
                    pendentes = 0
        logger.info("%-22s lidos=%4d carimbados=%4d", colecao, vistos, alterados)

    if not args.dry_run and pendentes:
        lote.commit()

    logger.info("Total alterado: %d", total_alterados)
    for slug, n in sorted(total_por_orgao.items()):
        logger.info("  %-14s %d", slug, n)
    if args.dry_run:
        print("\n(dry-run: nada foi gravado)")
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "carimbar_orgao"))
