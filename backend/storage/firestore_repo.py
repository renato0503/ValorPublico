from datetime import datetime, timezone

import pandas as pd

from config.settings import COLLECTION_AGENTES, SUBCOLLECTION_CLIPPINGS
from core.logger import get_logger

logger = get_logger(__name__)


class FirestoreRepo:
    """Repositorio de leitura/escrita no Firestore (agentes e clippings)."""

    def __init__(self, db) -> None:
        self.db = db

    def carregar_agentes(self, cidades: list[str] | None = None) -> list[dict]:
        query = self.db.collection(COLLECTION_AGENTES)
        if cidades:
            query = query.where("cidade", "in", cidades)
        docs = query.stream()
        return [{**doc.to_dict(), "id": doc.id} for doc in docs]

    def tem_clippings(self, agente_id: str) -> bool:
        """True se a subcolecao clippings do agente possui ao menos 1 doc."""
        it = (
            self.db.collection(COLLECTION_AGENTES)
            .document(agente_id)
            .collection(SUBCOLLECTION_CLIPPINGS)
            .limit(1)
            .stream()
        )
        return next(it, None) is not None

    @staticmethod
    def _id_clipping(registro: dict) -> str:
        return f"{registro['plataforma']}_{registro['id_externo']}"

    def salvar_clipping(self, agente_id: str, registro: dict) -> str:
        ref = (
            self.db.collection(COLLECTION_AGENTES)
            .document(agente_id)
            .collection(SUBCOLLECTION_CLIPPINGS)
            .document(self._id_clipping(registro))
        )
        ref.set(registro, merge=True)
        return ref.id

    def salvar_lote(self, df: pd.DataFrame) -> int:
        """Grava clippings em lotes transacionais de ate 500 documentos."""
        if df.empty:
            return 0
        total = 0
        lote: list[dict] = []
        for _, row in df.iterrows():
            lote.append(row.to_dict())
            if len(lote) == 500:
                total += self._flush(lote)
                lote = []
        if lote:
            total += self._flush(lote)
        logger.info("Firestore: %d clippings gravados.", total)
        return total

    def _flush(self, lote: list[dict]) -> int:
        batch = self.db.batch()
        for registro in lote:
            agente_id = registro.pop("agente_id")
            ref = (
                self.db.collection(COLLECTION_AGENTES)
                .document(agente_id)
                .collection(SUBCOLLECTION_CLIPPINGS)
                .document(self._id_clipping(registro))
            )
            batch.set(ref, registro, merge=True)
        batch.commit()
        return len(lote)

    def registrar_ultimo_scrape(self, resumo: dict) -> None:
        doc = {
            "executado_em": datetime.now(timezone.utc),
            **resumo,
        }
        self.db.collection("execucoes_ingestao").add(doc)