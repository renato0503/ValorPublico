from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from config.settings import FIREBASE_DATABASE_URL, FIREBASE_SERVICE_ACCOUNT
from core.logger import get_logger

logger = get_logger(__name__)

_app = None
_db = None


def init_firebase(
    service_account_path: str | None = None,
    database_url: str | None = None,
) -> firestore.Client:
    """Inicializa o Firebase Admin SDK e retorna o cliente Firestore."""
    global _app, _db

    if _app is not None:
        return _db

    path = Path(service_account_path or FIREBASE_SERVICE_ACCOUNT)
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo de conta de servico nao encontrado: {path}. "
            "Configure FIREBASE_SERVICE_ACCOUNT no .env"
        )

    cred = credentials.Certificate(str(path))
    _app = firebase_admin.initialize_app(
        cred, {"databaseURL": database_url or FIREBASE_DATABASE_URL}
    )
    _db = firestore.client()
    logger.info("Firebase inicializado com sucesso.")
    return _db


def get_db() -> firestore.Client:
    """Retorna o cliente Firestore, inicializando-o se necessario."""
    if _db is None:
        return init_firebase()
    return _db