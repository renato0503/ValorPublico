"""Gera/atualiza a tabela de valoração de mídia no Firestore.

Coleção `tabela_midia`, documento `geral`:
  - `cpm`: R$ por mil impressões (alcance) para cada plataforma de rede social.
  - `veiculos`: valor de referência (R$/matéria) por veículo de notícia (Web).

Estes são VALORES DE REFERÊNCIA iniciais — ajuste conforme a tabela real de
cada veículo (através do Console ou editando este script).

Uso: python backend/scripts/seed_tabela_midia.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

COLLECTION_TABELA = "tabela_midia"

# CPM: custo por mil impressões (R$) — usado p/ plataformas com alcance (views).
CPM_PLATAFORMAS = {
    "Twitter": 18.0,
    "Instagram": 22.0,
    "Facebook": 15.0,
    "YouTube": 25.0,
    "Telegram": 12.0,
    "TikTok": 20.0,
    "TV": 40.0,
    "Radio": 18.0,
}

# Valor de referência (R$) por matéria/veículo — mídia tradicional (Web).
# Ajuste conforme a tabela publicitária real de cada veículo.
VALOR_PADRAO_PORTAL = 400.0

VEICULOS = {
    "g1": {"valor_referencia": 800.0, "tipo": "portal", "unidade": "materia"},
    "gazeta digital": {"valor_referencia": 500.0, "tipo": "portal", "unidade": "materia"},
    "rd news": {"valor_referencia": 350.0, "tipo": "portal", "unidade": "materia"},
    "olhar direto": {"valor_referencia": 300.0, "tipo": "portal", "unidade": "materia"},
    "folhamax": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia"},
    "diário de cuiabá": {"valor_referencia": 450.0, "tipo": "portal", "unidade": "materia"},
    "midianews": {"valor_referencia": 300.0, "tipo": "portal", "unidade": "materia"},
    "republic news": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia"},
    "várzea grande 24 horas": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia"},
    "portal várzea grande": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia"},
}

# Veículos de mídia impressa (jornais com edição digital) — R$/matéria.
IMPRESSOS = {
    "diario de cuiaba": {"valor_referencia": 500.0, "tipo": "impresso", "unidade": "materia"},
    "a gazeta": {"valor_referencia": 600.0, "tipo": "impresso", "unidade": "materia"},
    "folha do estado": {"valor_referencia": 450.0, "tipo": "impresso", "unidade": "materia"},
}


def main() -> None:
    db = init_firebase()
    veiculos = {**VEICULOS, **IMPRESSOS}
    doc = {
        "cpm": CPM_PLATAFORMAS,
        "veiculos": veiculos,
        "impressos": IMPRESSOS,
        "valor_padrao_portal": VALOR_PADRAO_PORTAL,
        "atualizado_em": datetime.now(timezone.utc),
    }
    db.collection(COLLECTION_TABELA).document("geral").set(doc, merge=True)
    logger.info(
        "Tabela de midia gravada: %d plataformas (CPM) + %d veiculos.",
        len(CPM_PLATAFORMAS), len(veiculos),
    )


if __name__ == "__main__":
    main()