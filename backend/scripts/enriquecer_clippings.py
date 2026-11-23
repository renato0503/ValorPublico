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
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (  # noqa: E402
    COLLECTION_AGENTES,
    COMPLIANCE_ELEITORAL_ENABLED,
    SUBCOLLECTION_CLIPPINGS,
)
from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.quota import main_com_cota  # noqa: E402
from processing.enriquecimento import (  # noqa: E402
    campos_para_salvar,
    enriquecer_clipping,
)
from processing.valoracao import Valorador  # noqa: E402

logger = get_logger(__name__)


def _campos_valoracao(valorador: Valorador, clipping: dict) -> dict:
    """Calcula AVPE, centimetragem e duracao para clippings ja gravados."""
    metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
    veiculo = metadados.get("veiculo") or clipping.get("autor") or ""
    plataforma = clipping.get("plataforma", "")
    espaco_cm2 = float(metadados.get("espaco_cm2") or 0.0)
    duracao_seg = float(metadados.get("duracao_seg") or 0.0)
    if not espaco_cm2 and plataforma == "Impresso":
        espaco_cm2 = round(float(metadados.get("espaco_carac") or 0.0) / 12.0, 2)
    if not duracao_seg and plataforma in ("TV", "Radio", "YouTube"):
        duracao_seg = round(len(str(clipping.get("texto_limpo") or "")) / 15.0, 1)
    return {
        "valor_avpe": valorador.avpe(
            plataforma, veiculo, espaco_cm2, duracao_seg, int(clipping.get("alcance") or 0)
        ),
        "espaco_cm2": round(espaco_cm2, 2),
        "duracao_seg": round(duracao_seg, 1),
    }


def main() -> None:
    db = init_firebase()
    valorador = Valorador(db)
    forcar = "--forcar" in sys.argv
    limite = 0
    filtro = ""
    for arg in sys.argv:
        if arg.startswith("--agentes="):
            filtro = arg.split("=", 1)[1]
        if arg.startswith("--limite="):
            limite = int(arg.split("=", 1)[1])
    ids_filtro = {i.strip() for i in filtro.split(",") if i.strip()}

    total = 0
    atualizados = 0
    lote: list = []
    refs: list = []

    def _descartar_lote() -> None:
        nonlocal lote, refs, atualizados
        if not lote:
            return
        for tentativa in range(1, 6):
            try:
                batch = db.batch()
                for ref, dados in zip(refs, lote):
                    batch.update(ref, dados)
                batch.commit()
                break
            except Exception as e:  # noqa: BLE001
                if tentativa == 5:
                    logger.error("Lote descartado apos 5 tentativas: %s", e)
                    break
                espera = 5 * tentativa
                logger.warning("Lote falhou (tentativa %d): %s. Nova tentativa em %ds.",
                               tentativa, e, espera)
                time.sleep(espera)
        atualizados += len(lote)
        lote = []
        refs = []

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
            if limite and total > limite:
                break
            dados = clip.to_dict() or {}
            if not forcar and dados.get("mencao") and dados.get("trecho") and "valor_avpe" in dados:
                continue
            enriquecido = enriquecer_clipping(
                dados,
                agente=agente,
                compliance_habilitado=COMPLIANCE_ELEITORAL_ENABLED,
            )
            campos = campos_para_salvar(enriquecido)
            campos.update(_campos_valoracao(valorador, dados))
            if not any(campos.values()):
                continue
            lote.append(campos)
            refs.append(clip.reference)
            if len(lote) >= 400:
                _descartar_lote()
        if limite and total > limite:
            break
    _descartar_lote()

    logger.info(
        "Enriquecimento concluido: %d clippings lidos, %d atualizados.", total, atualizados
    )
    logger.info(
        "Enriquecimento concluido: %d clippings lidos, %d atualizados.", total, atualizados
    )


if __name__ == "__main__":
    main_com_cota(main, "enriquecer_clippings")

