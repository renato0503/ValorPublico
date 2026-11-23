"""Ingere o radar de propaganda publica (fontes oficiais de MT).

Coleta as fontes definidas em `FONTES_PROPAGANDA_PUBLICA` (padrao: Cuiaba,
Varzea Grande e Assembleia/Estado de MT - ver config/fontes_radar.py) e grava
na colecao `radar_publico/clippings`, que alimenta o painel "Radar de propaganda
publica" e o compliance eleitoral (uso de simbolos publicos, art. 40).

Idempotente: o id do documento e o hash da URL/texto, entao rodar duas vezes
nao duplica nada.

Uso:
    python scripts/ingerir_radar.py
    python scripts/ingerir_radar.py --max 40
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (  # noqa: E402
    FONTES_PROPAGANDA_PUBLICA,
    HABILITAR_PROPAGANDA_PUBLICA,
    PROPAGANDA_PUBLICA_MAX_ITENS,
)
from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.quota import main_com_cota  # noqa: E402
from processing.propaganda_publica import (  # noqa: E402
    CLASSE_PUBLICACAO_OFICIAL,
    detectar,
)
from scraper.propaganda_publica_scraper import PropagandaPublicaScraper  # noqa: E402

logger = get_logger(__name__)

COLECAO_RADAR = "radar_publico"
SUBCOLLECAO = "clippings"

# Vincula a fonte oficial ao municipio correspondente (radar por escopo)
CIDADE_POR_DOMINIO = {
    "cuiaba.mt.gov.br": "Cuiaba",
    "camaracuiaba.mt.gov.br": "Cuiaba",
    "transparencia.cuiaba.mt.gov.br": "Cuiaba",
    "varzeagrande.mt.gov.br": "Varzea Grande",
}


def _cidade_do_item(url: str) -> str:
    alvo = (url or "").lower()
    for dominio, cidade in CIDADE_POR_DOMINIO.items():
        if dominio in alvo:
            return cidade
    return ""


def main() -> None:
    if not HABILITAR_PROPAGANDA_PUBLICA:
        logger.info(
            "Radar desabilitado (HABILITAR_PROPAGANDA_PUBLICA=0). "
            "Ative para coletar as fontes oficiais."
        )
        return

    max_itens = PROPAGANDA_PUBLICA_MAX_ITENS
    for arg in sys.argv:
        if arg.startswith("--max="):
            max_itens = int(arg.split("=", 1)[1])

    db = init_firebase()
    scraper = PropagandaPublicaScraper(
        config={
            "fontes": FONTES_PROPAGANDA_PUBLICA,
            "max_itens": max_itens,
            "delay_min": 2.0,
            "delay_max": 5.0,
        }
    )

    total = 0
    for fonte in FONTES_PROPAGANDA_PUBLICA:
        try:
            itens = scraper._coletar_fonte(fonte, 0, max_itens)
        except Exception as e:  # noqa: BLE001
            logger.error("Falha ao coletar o radar em %s: %s", fonte, e)
            continue
        for item in itens:
            radar = detectar({"texto_limpo": item.texto_limpo, "metadados": item.metadados})
            documento = {
                **item.to_dict(),
                "cidade": _cidade_do_item(item.url) or _cidade_do_item(fonte),
                "radar": radar,
                # Item de canal oficial: e o objeto do radar, mesmo que o texto
                # nao se pareca com propaganda.
                "classe": CLASSE_PUBLICACAO_OFICIAL,
                "classe_semantica": radar.get("classe", ""),
                "orgao": radar.get("orgao") or item.metadados.get("orgao", ""),
                "tipo": radar.get("tipo", "") or "comunicacao_institucional",
                "simbolos_publicos": radar.get("simbolos_publicos", False),
                "created_at": datetime.now(timezone.utc),
            }
            documento.pop("agente_id", None)
            ref = db.collection(COLECAO_RADAR).document(item.id_externo)
            ref.set(documento, merge=True)
            total += 1
        logger.info("Radar: %s -> %d itens", fonte, len(itens))

    logger.info("Radar de propaganda publica gravado: %d itens em %s.",
                total, COLECAO_RADAR)


if __name__ == "__main__":
    main_com_cota(main, "ingerir_radar")



