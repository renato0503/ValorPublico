"""Grava um usuario administrador (owner) na colecao 'usuarios' do Firestore.

O documento e identificado pelo UID do Firebase Authentication, permitindo
que o frontend verifique o papel (papel == "owner") para liberar acesso total.

Uso: python backend/scripts/criar_owner.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

COLLECTION_USUARIOS = "usuarios"

# Usuario do Firebase Authentication fornecido pelo proprietario
OWNER = {
    "uid": "PS7XKpuuQHdw4wUsTjkxwhHBJfC3",
    "email": "gestor.renatorosa@gmail.com",
    "nome": "Renato Rosa",
    "papel": "owner",
    "ativo": True,
}


def main() -> None:
    db = init_firebase()
    agora = datetime.now(timezone.utc)

    doc = {
        **OWNER,
        "criado_em": agora,
        "atualizado_em": agora,
    }

    ref = db.collection(COLLECTION_USUARIOS).document(OWNER["uid"])
    ref.set(doc, merge=True)
    logger.info(
        "Usuario gravado como '%s' em usuarios/%s (%s).",
        doc["papel"], OWNER["uid"], doc["email"],
    )


if __name__ == "__main__":
    main()