"""Mede o passo do discurso em dois modelos (decisao D2, plano 15 §4).

Uso (a partir de `backend/`, com `ollama serve` no ar):
    python scripts/medir_modelos.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.processing import textos_graficos

logger = get_logger(__name__)

BRIEFING = {
    "escopo": "agente-teste",
    "semana": "2026-W48",
    "classes": [
        {"id": 1, "pct": 34.0, "forma": "saude", "chi2": 45.2, "formas": ["upa", "fila", "medico"]},
        {"id": 2, "pct": 22.0, "forma": "obras", "chi2": 25.0, "formas": ["asfalto", "ponte"]},
    ],
    "fatos": [
        {"id": "c1", "texto": "O grupo saude ocupa 34% dos segmentos", "fonte": "IRaMuTeQ"},
        {"id": "c2", "texto": "O grupo obras ocupa 22% dos segmentos", "fonte": "IRaMuTeQ"},
    ],
    "demandas_top": ["mais profissionais de saude na UPA"],
    "tendencias": ["aumento de busca por saude publica"],
    "tese": "A prioridade da semana e a saude e a obra da ponte",
}


def medir(modelo: str, url: str = "http://127.0.0.1:11434") -> dict:
    inicio = time.monotonic()
    resultado = textos_graficos.gerar_discurso(
        BRIEFING, formato="tribuna", modelo=modelo, url_ollama=url, timeout=600
    )
    duracao = time.monotonic() - inicio
    texto = resultado.get("texto", "")
    return {
        "modelo": modelo,
        "segundos": round(duracao, 1),
        "caracteres": len(texto),
        "palavras": len(texto.split()),
        "ok": resultado.get("ok", False),
        "fontes": resultado.get("fontes", []),
        "amostra": texto[:220],
    }


def main() -> int:
    modelos = sys.argv[1:] or ["qwen3:8b", "gemma4:latest"]
    saida = []
    for modelo in modelos:
        logger.info("Medindo %s ...", modelo)
        saida.append(medir(modelo))
        logger.info("  %s: %.1f s (%d palavras)", modelo, saida[-1]["segundos"], saida[-1]["palavras"])

    destino = Path("data/semanal/medicao_modelos.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Medicao gravada em %s", destino)
    for item in saida:
        print(f"  {item['modelo']:18s} {item['segundos']:6.1f}s  {item['palavras']:4d} palavras  ok={item['ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
