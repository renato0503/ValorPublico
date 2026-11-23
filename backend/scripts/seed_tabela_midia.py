"""Gera/atualiza a tabela de valoração de mídia no Firestore.

Coleção `tabela_midia`, documento `geral`:
  - `cpm`: R$ por mil impressões (alcance) para cada plataforma de rede social.
  - `veiculos`: valor de referência (R$/matéria) por veículo de notícia (Web/Impresso).
  - `bases_valoracao`: faixas de referência por tipo de mídia (DSM-style).

Estes são VALORES DE REFERÊNCIA — baseados nas faixas de mercado 2025/2026
(tabelas SINAPRO, mídia-kit de veículos regionais e CPM de plataformas digitais).
Ajuste fino: edite este script (ou o Console) com a tabela publicitária real de
cada veículo quando disponível.

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
# Referência de mercado 2025/2026 (display/vídeo social no Brasil).
CPM_PLATAFORMAS = {
    "Twitter": 18.0,
    "Instagram": 22.0,
    "Facebook": 15.0,
    "YouTube": 25.0,
    "Telegram": 12.0,
    "TikTok": 20.0,
    "Linkedin": 25.0,
    "Kwai": 12.0,
    "TV": 40.0,
    "Radio": 18.0,
}

# Valor de referência (R$) por matéria/veículo — mídia tradicional (Web/Impresso).
# Campos por veículo:
#   valor_referencia  -> R$ por unidade de valoração
#   tipo              -> portal | impresso | tv | radio | governo
#   unidade           -> materia (R$/matéria) ou cm2 (R$/cm² impresso)
#   fonte             -> origem do valor de referência (para auditoria)
VALOR_PADRAO_PORTAL = 350.0
VALOR_PADRAO_JORNAL = 500.0

VEICULOS = {
    # --- Mato Grosso: portais (alcance local) ---
    "g1": {"valor_referencia": 900.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "g1 mt": {"valor_referencia": 600.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional regional"},
    "gazeta digital": {"valor_referencia": 500.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "rd news": {"valor_referencia": 400.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "rdnews": {"valor_referencia": 400.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "olhar direto": {"valor_referencia": 350.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "folhamax": {"valor_referencia": 300.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "diário de cuiabá": {"valor_referencia": 500.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "diario de cuiabá": {"valor_referencia": 500.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "midianews": {"valor_referencia": 350.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "caldeirão político": {"valor_referencia": 300.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "o diário mt": {"valor_referencia": 300.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "odiariomt.com.br": {"valor_referencia": 300.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "midiajur": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "midiajur.com.br": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "cuiabá notícias": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "cuiabanoticias": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "várzea grande 24 horas": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "portal várzea grande": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "vgnoticias.com.br": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "agora mt": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "repórtermt": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "mato grosso mais": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "primeira página": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "hipernotícias": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "o bom da notícia": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "o documento": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "o mato grosso": {"valor_referencia": 250.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "baixada cuiabana news": {"valor_referencia": 150.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "passandoalimpomt.com.br": {"valor_referencia": 150.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "mtagora.com.br": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "a bronca popular": {"valor_referencia": 150.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    "agenda do poder": {"valor_referencia": 200.0, "tipo": "portal", "unidade": "materia", "fonte": "tabela veículo"},
    # --- Nacionais: portais (alcance amplo) ---
    "uol": {"valor_referencia": 1200.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "metrópoles": {"valor_referencia": 800.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "poder360": {"valor_referencia": 700.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "congresso em foco": {"valor_referencia": 600.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "pleno.news": {"valor_referencia": 500.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "o livre": {"valor_referencia": 400.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
    "midiamax": {"valor_referencia": 400.0, "tipo": "portal", "unidade": "materia", "fonte": "portal nacional"},
}

# Veículos de mídia impressa (jornais com edição digital) — R$/matéria.
IMPRESSOS = {
    "diario de cuiaba": {"valor_referencia": 500.0, "tipo": "impresso", "unidade": "materia", "fonte": "tabela veículo"},
    "a gazeta": {"valor_referencia": 600.0, "tipo": "impresso", "unidade": "materia", "fonte": "tabela veículo"},
    "folha do estado": {"valor_referencia": 450.0, "tipo": "impresso", "unidade": "materia", "fonte": "tabela veículo"},
    "o globo": {"valor_referencia": 1500.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "folha de s.paulo": {"valor_referencia": 1500.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "estadão": {"valor_referencia": 1400.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "valor econômico": {"valor_referencia": 1300.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "correio braziliense": {"valor_referencia": 1000.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "gazeta do povo": {"valor_referencia": 700.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "correio do povo": {"valor_referencia": 600.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
    "o tempo": {"valor_referencia": 500.0, "tipo": "impresso", "unidade": "materia", "fonte": "jornais nacionais"},
}

# Faixas de valoração por tipo de mídia — base utilizada para veículos sem
# valor específico na tabela (modelo DSM: espaço x valor de referência).
# `valor_por_cm2` (impresso) e `valor_por_minuto` (TV/rádio) permitem calcular
# centimetragem e AVPE a partir do espaço ocupado e da duração do clipping.
BASES_VALORACAO = {
    "portal": {"padrao": VALOR_PADRAO_PORTAL, "unidade": "materia", "faixa": [150.0, 1500.0]},
    "impresso": {
        "padrao": VALOR_PADRAO_JORNAL,
        "unidade": "materia",
        "faixa": [250.0, 1500.0],
        "valor_por_cm2": 22.0,
    },
    "tv": {
        "padrao": 800.0,
        "unidade": "materia",
        "faixa": [400.0, 3000.0],
        "valor_por_minuto": 320.0,
    },
    "radio": {
        "padrao": 300.0,
        "unidade": "materia",
        "faixa": [150.0, 800.0],
        "valor_por_minuto": 120.0,
    },
    "governo": {"padrao": 0.0, "unidade": "materia", "faixa": [0.0, 0.0]},
}


def main() -> None:
    db = init_firebase()
    veiculos = {**VEICULOS, **IMPRESSOS}
    doc = {
        "cpm": CPM_PLATAFORMAS,
        "veiculos": veiculos,
        "impressos": IMPRESSOS,
        "bases_valoracao": BASES_VALORACAO,
        "valor_padrao_portal": VALOR_PADRAO_PORTAL,
        "atualizado_em": datetime.now(timezone.utc),
    }
    db.collection(COLLECTION_TABELA).document("geral").set(doc, merge=True)
    logger.info(
        "Tabela de midia gravada: %d plataformas (CPM) + %d veiculos (%d portais, %d impressos).",
        len(CPM_PLATAFORMAS), len(veiculos), len(VEICULOS), len(IMPRESSOS),
    )


if __name__ == "__main__":
    main()