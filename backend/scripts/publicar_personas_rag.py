"""Atualiza as personas no Firestore quando a RAG e publicada.

Le `simulacao/personas_export/manifest.json` e grava `rag_version`/`status`
em `personas/{id}`. Nao sobe a RAG para o Firestore (o pacote fica na API).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)
MANIFEST = Path(__file__).resolve().parents[3] / "simulacao" / "personas_export" / "manifest.json"


def main() -> int:
    if not MANIFEST.exists():
        logger.error("Manifesto RAG ausente: %s", MANIFEST)
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    versao = manifest.get("versao_rag", "")
    db = init_firebase()
    lote = db.batch()
    total = 0
    for item in manifest.get("personas", []):
        lote.set(
            db.collection("personas").document(item["id"]),
            {
                "rag_version": versao,
                "status": "online",
                "atualizado_em": datetime.now(timezone.utc),
            },
            merge=True,
        )
        total += 1
    lote.commit()
    logger.info("Personas atualizadas: %d (rag=%s).", total, versao)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
