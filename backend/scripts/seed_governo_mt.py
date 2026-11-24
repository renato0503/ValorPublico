"""Grava as entidades do Governo de Mato Grosso no Firestore (ValorPublico).

Cria (com merge=True, em lote de 400):
  * `governo-mt`                  -> o Governo do Estado como um todo
  * `governador-otaviano-pivetta`  -> o governador (pessoa)
  * `interino-max-russi`          -> o governador interino (condicional)

Nao mexe nos vereadores nem nos deputados (muralha de dados: um orgao por vez).
Cada documento tem `casa = "Governo MT"`, que o front usa para separar o
Executivo das Camaras e da ALMT.

Uso (a partir de `backend/`):
    python scripts/seed_governo_mt.py --dry-run
    python scripts/seed_governo_mt.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import BASE_DIR, COLLECTION_AGENTES
from core.logger import get_logger

logger = get_logger(__name__)

SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"
LOTE = 400


def _termos(*itens: str) -> list[str]:
    vistos = set()
    for item in itens:
        for parte in str(item or "").split(","):
            parte = parte.strip()
            if parte:
                vistos.add(parte)
    return sorted(vistos)


def montar_documentos(seed: dict) -> list[tuple[str, dict]]:
    orgao = seed.get("orgao", {})
    docs: list[tuple[str, dict]] = []

    # 1) o Governo do Estado como um todo
    termos_gov = _termos(
        "governo de mato grosso",
        "governo do estado de mato grosso",
        "governo mt",
        "governo do estado",
        "palacio paiaguas",
        "estado de mato grosso",
        "executivo estadual",
    )
    docs.append(
        (
            "governo-mt",
            {
                "nome_urna": "Governo do Estado de Mato Grosso",
                "cidade": orgao.get("cidade", "Governo de Mato Grosso"),
                "casa": orgao.get("casa", "Governo MT"),
                "esfera": orgao.get("esfera", "estadual-executivo"),
                "cargo": "Governo do Estado",
                "genero": "N",
                "partido": "",
                "tipo_entidade": "orgao",
                "nivel": "governo",
                "sigla": orgao.get("sigla", "GOVERNO MT"),
                "vigente_desde": orgao.get("vigente_desde", ""),
                "fonte_oficial": orgao.get("site", ""),
                "fonte_orgaos_publicos": seed.get("consulta_orgaos_completos", {}).get("url", ""),
                "termos_de_busca": termos_gov,
            },
        )
    )

    # 2) o governador
    governador = seed.get("governador", {})
    if governador:
        docs.append(
            (
                governador["slug"],
                {
                    "nome_urna": governador["nome"],
                    "cidade": orgao.get("cidade", "Governo de Mato Grosso"),
                    "casa": orgao.get("casa", "Governo MT"),
                    "esfera": orgao.get("esfera", "estadual-executivo"),
                    "cargo": governador.get("cargo", "Governador do Estado"),
                    "genero": "M",
                    "partido": governador.get("partido", ""),
                    "tipo_entidade": "pessoa",
                    "nivel": "governador",
                    "vigente_desde": orgao.get("vigente_desde", ""),
                    "fonte_oficial": orgao.get("site", ""),
                    "termos_de_busca": _termos(*governador.get("termos", [])),
                },
            )
        )

    # 3) o interino (condicional)
    interino = seed.get("interino", {})
    if interino:
        docs.append(
            (
                interino["slug"],
                {
                    "nome_urna": interino["nome"],
                    "cidade": orgao.get("cidade", "Governo de Mato Grosso"),
                    "casa": orgao.get("casa", "Governo MT"),
                    "esfera": orgao.get("esfera", "estadual-executivo"),
                    "cargo": interino.get("cargo", "Governador Interino"),
                    "genero": "M",
                    "partido": "",
                    "tipo_entidade": "pessoa",
                    "nivel": "interino",
                    "condicional": True,
                    "vigente_desde": orgao.get("vigente_desde", ""),
                    "fonte_oficial": seed.get("interino", {}).get("fonte", {}).get("url", ""),
                    "termos_de_busca": _termos(*interino.get("termos", [])),
                },
            )
        )

    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed das entidades do Governo de MT.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    docs = montar_documentos(seed)

    for doc_id, dados in docs:
        print(f"  {doc_id:38s} casa={dados['casa']:12s} cargo={dados['cargo']}")
        print(f"      termos: {len(dados['termos_de_busca'])}")

    if args.dry_run:
        print("\n(dry-run: nada foi gravado)")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    colecao = db.collection(COLLECTION_AGENTES)
    lote = db.batch()
    total = 0
    for doc_id, dados in docs:
        lote.set(colecao.document(doc_id), dados, merge=True)
        total += 1
        if total % LOTE == 0:
            lote.commit()
            lote = db.batch()
    if total % LOTE:
        lote.commit()
    logger.info("Entidades gravadas: %d", total)

    contagem = colecao.count().get()
    total_agentes = contagem[0][0].value if isinstance(contagem[0], list) else contagem[0].value
    logger.info("Total em %s: %s", COLLECTION_AGENTES, total_agentes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
