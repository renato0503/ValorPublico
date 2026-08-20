"""Apaga TODOS os documentos e subcolecoes do projeto Firestore.

Cuidado: operacao irreversivel. Use apenas em ambiente de desenvolvimento.

Uso: python backend/scripts/zerar_firestore.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

COLECOES_RAIZ = [
    "agentes_publicos",
    "usuarios",
    "metricas",
    "metricas_por_cidade",
    "metricas_por_agente",
    "metricas_diarias",
    "tabela_midia",
    "execucoes_ingestao",
]
SUBCOLECOES = ["clippings"]


def apagar_documento(doc_ref) -> None:
    """Apaga um documento e TODAS as suas subcolecoes (recursivamente)."""
    for sub in SUBCOLECOES:
        for sdoc in doc_ref.collection(sub).stream():
            sdoc.reference.delete()
    doc_ref.delete()


def apagar_colecao(db, nome: str) -> int:
    ref = db.collection(nome)
    docs = list(ref.stream())
    for d in docs:
        apagar_documento(d.reference)
    return len(docs)


def main() -> None:
    db = init_firebase()
    total = 0
    for colecao in COLECOES_RAIZ:
        removidos = apagar_colecao(db, colecao)
        total += removidos
        logger.info("Colecao '%s' -> %d documentos removidos.", colecao, removidos)
    logger.info("Limppeza concluida. Total de documentos removidos: %d", total)


if __name__ == "__main__":
    main()