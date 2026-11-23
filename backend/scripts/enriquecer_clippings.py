"""Backfill da Camada DSM: Enriquece os clippings ja gravados.

Adiciona a cada documento da subcolecao `clippings` os campos de inteligencia:
`mencao` (direta/indireta/indeterminada + papel + porta-vozes), `trecho`
(recorte citado), `compliance` (Lei 9.504/1997) e `propaganda_publica`
(radar). Idempotente: so escreve o que ainda falta.

Uso:
    python scripts/enriquecer_clippings.py            # todos os agentes
    python scripts/enriquecer_clippings.py --agentes a,b
    python scripts/enriquecer_clippings.py --forcar     # reescreve tudo
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (  # noqa: E402
    COLLECTION_AGENTES,
    COMPLIANCE_ELEITORAL_ENABLED,
    SUBCOLLECTION_CLIPPINGS,
)
from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from processing.enriquecimento import (  # noqa: E402
    campos_para_salvar,
    enriquecer_clipping,
)

logger = get_logger(__name__)


def main() -> None:
    db = init_firebase()
    forcar = "--forcar" in sys.argv
    filtro = ""
    for arg in sys.argv:
        if arg.startswith("--agentes="):
            filtro = arg.split("=", 1)[1]
    ids_filtro = {i.strip() for i in filtro.split(",") if i.strip()}

    total = 0
    atualizados = 0
    for agente_ref in db.collection(COLLECTION_AGENTES).stream():
        if ids_filtro and agente_ref.id not in ids_filtro:
            continue
        agente = agente_ref.to_dict() or {}
        sub = (
            db.collection(COLLECTION_AGENTES)
            .document(agente_ref.id)
            .collection(SUBCOLLECTION_CLIPPINGS)
        )
        for clip in sub.stream():
            total += 1
            dados = clip.to_dict() or {}
            if not forcar and dados.get("mencao") and dados.get("trecho"):
                continue
            enriquecido = enriquecer_clipping(
                dados,
                agente=agente,
                compliance_habilitado=COMPLIANCE_ELEITORAL_ENABLED,
            )
            campos = campos_para_salvar(enriquecido)
            if not any(campos.values()):
                continue
            clip.reference.update(campos)
            atualizados += 1
    logger.info(
        "Enriquecimento concluido: %d clippings lidos, %d atualizados.", total, atualizados
    )


if __name__ == "__main__":
    main()
