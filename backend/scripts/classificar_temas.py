"""Backfill: classifica cada clipping existente em temas/categorias.

Adiciona o campo `categorias` (array de temas) em cada documento da subcoleção
`clippings`. Idempotente: nao duplica temas ja existentes.

Uso: python scripts/classificar_temas.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import COLLECTION_AGENTES, SUBCOLLECTION_CLIPPINGS
from core.firebase_client import init_firebase
from core.logger import get_logger
from processing.temas import classificar_temas

logger = get_logger(__name__)


def main() -> None:
    db = init_firebase()
    total = 0
    agentes = db.collection(COLLECTION_AGENTES).stream()
    for agente in agentes:
        sub = (
            db.collection(COLLECTION_AGENTES)
            .document(agente.id)
            .collection(SUBCOLLECTION_CLIPPINGS)
        )
        for clip in sub.stream():
            dados = clip.to_dict()
            texto = dados.get("texto_limpo", "")
            temas = classificar_temas(texto)
            if not temas:
                continue
            atuais = set(dados.get("categorias") or [])
            novos = [t for t in temas if t not in atuais]
            if not novos:
                continue
            clip.reference.update({"categorias": sorted(atuais | set(temas))})
            total += 1
    logger.info("Backfill de temas concluido: %d clippings atualizados.", total)


if __name__ == "__main__":
    main()