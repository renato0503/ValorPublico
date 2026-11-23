from pathlib import Path

import json

import firebase_admin
from firebase_admin import credentials, firestore

from config.settings import (
    FIREBASE_DATABASE_URL,
    FIREBASE_PROJECT_ID,
    FIREBASE_SERVICE_ACCOUNT,
)
from core.logger import get_logger

logger = get_logger(__name__)

_app = None
_db = None


def _validar_projeto(path: Path, projeto_esperado: str) -> None:
    """Aborta se a credencial apontar para outro projeto Firestore (achado A1)."""
    if not projeto_esperado:
        logger.warning(
            "FIREBASE_PROJECT_ID nao definido: validacao do projeto da credencial "
            "desativada."
        )
        return
    with path.open(encoding="utf-8") as fh:
        projeto_credencial = json.load(fh).get("project_id", "")
    if projeto_credencial != projeto_esperado:
        raise RuntimeError(
            f"Credencial de servico aponta para o projeto '{projeto_credencial}', "
            f"mas FIREBASE_PROJECT_ID='{projeto_esperado}'. Abortando para evitar "
            "leitura/escrita no Firestore errado. Gere a chave no projeto correto "
            "no Firebase Console (Contas de servico) e salve em "
            f"{path}."
        )


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

    _validar_projeto(path, FIREBASE_PROJECT_ID)
    cred = credentials.Certificate(str(path))
    _app = firebase_admin.initialize_app(
        cred, {"databaseURL": database_url or FIREBASE_DATABASE_URL}
    )
    _db = firestore.client()
    logger.info(
        "Firebase inicializado com sucesso (projeto %s).", FIREBASE_PROJECT_ID
    )
    return _db


def get_db() -> firestore.Client:
    """Retorna o cliente Firestore, inicializando-o se necessario."""
    if _db is None:
        return init_firebase()
    return _db