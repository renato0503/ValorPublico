"""Reclassifica o sentimento dos clippings historicos com a IA (backfill).

Requisitos: `IA_SENTIMENTO_ENABLED=1` e `IA_SENTIMENTO_API_KEY` no `.env`.
Sem IA configurada, use `--forcar-vader` apenas para reprocessar tudo com VADER.

Uso:
    python scripts/reclassificar_sentimentos.py --plano        # mostra custo estimado, nao grava
    python scripts/reclassificar_sentimentos.py --aplicar      # classifica e grava
    python scripts/reclassificar_sentimentos.py --aplicar --limite 500
    python scripts/reclassificar_sentimentos.py --aplicar --forcar-vader
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger
from processing.sentimento_ia import AnalisadorSentimentoIA

logger = get_logger(__name__)

# Custo estimado p/ calculo do plano (gpt-4o-mini aprox., 2026).
# Entrada ~US$ 0.15 / 1M tokens; saida ~US$ 0.60 / 1M tokens.
CUSTO_INPUT_1K = 0.15 / 1000
CUSTO_OUTPUT_1K = 0.60 / 1000
TOKENS_OUTPUT_POR_ITEM = 6  # JSON curto por item


def carregar_clippings(db) -> list[dict]:
    """Retorna todos os clippings com referencia, texto e sentimento atual."""
    clippings: list[dict] = []
    for agente in db.collection(settings.COLLECTION_AGENTES).stream():
        for clip in agente.reference.collection(settings.SUBCOLLECTION_CLIPPINGS).stream():
            dados = clip.to_dict()
            texto = (dados.get("texto_limpo") or "").strip()
            if not texto:
                continue
            clippings.append(
                {
                    "ref": clip.reference,
                    "texto": texto,
                    "atual": dados.get("sentimento"),
                }
            )
    return clippings


def estimar_tokens(texto: str) -> int:
    # Aproximacao: ~4 chars/token; corta no mesmo limite do prompt (600 chars)
    return max(1, len(texto[:600]) // 4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill do sentimento com IA.")
    parser.add_argument("--plano", action="store_true", help="Apenas estima custo e mostra distribuicao.")
    parser.add_argument("--aplicar", action="store_true", help="Classifica e grava as mudancas.")
    parser.add_argument("--limite", type=int, default=0, help="Limita a quantidade de clippings processados.")
    parser.add_argument("--forcar-vader", action="store_true", help="Usa VADER mesmo sem IA configurada.")
    args = parser.parse_args()

    if not args.plano and not args.aplicar:
        parser.error("Informe --plano ou --aplicar.")

    db = init_firebase()
    clippings = carregar_clippings(db)
    if args.limite > 0:
        clippings = clippings[: args.limite]
    logger.info("Clippings carregados: %d.", len(clippings))
    if not clippings:
        logger.warning("Nenhum clipping com texto para reclassificar.")
        return

    distrib = Counter(c["atual"] for c in clippings)
    logger.info("Distribuicao atual: %s", dict(distrib))

    if args.plano:
        tokens_input = sum(estimar_tokens(c["texto"]) for c in clippings)
        tokens_output = TOKENS_OUTPUT_POR_ITEM * len(clippings)
        custo = tokens_input * CUSTO_INPUT_1K + tokens_output * CUSTO_OUTPUT_1K
        print(
            f"Plano de reclassificacao ({len(clippings)} clippings):\n"
            f"  tokens de entrada (aprox.): {tokens_input:,}\n"
            f"  tokens de saida (aprox.):   {tokens_output:,}\n"
            f"  custo estimado (USD):       ${custo:.2f}\n"
            f"  modelo:                     {settings.IA_SENTIMENTO_MODEL or 'gpt-4o-mini'}\n"
            f"  distrib. atual:             {dict(distrib)}\n"
        )
        return

    analisador = AnalisadorSentimentoIA()
    if not analisador.habilitado and not args.forcar_vader:
        logger.error(
            "IA de sentimento nao configurada (IA_SENTIMENTO_ENABLED/API_KEY). "
            "Use --forcar-vader para reclassificar com VADER."
        )
        sys.exit(1)

    mudancas = 0
    total = len(clippings)
    for i in range(0, total, analisador.tamanho_lote):
        lote = clippings[i : i + analisador.tamanho_lote]
        textos = [c["texto"] for c in lote]
        rotulos = analisador.classificar_lote(textos)

        batch = db.batch()
        n_lote = 0
        for clip, novo in zip(lote, rotulos):
            if novo == clip["atual"]:
                continue
            batch.update(clip["ref"], {"sentimento": novo})
            mudancas += 1
            n_lote += 1
            if n_lote >= 450:  # limite seguro do batch (500 docs)
                batch.commit()
                batch = db.batch()
                n_lote = 0
        if n_lote:
            batch.commit()
        if (i // analisador.tamanho_lote + 1) % 5 == 0 or i + len(lote) >= total:
            logger.info("Progresso: %d/%d | mudancas: %d", i + len(lote), total, mudancas)

    logger.info(
        "Backfill concluido: %d/%d clippings reclassificados. IA=%d fallback=%d.",
        mudancas, total, analisador._estatisticas["ia"], analisador._estatisticas["fallback_vader"],
    )


if __name__ == "__main__":
    main()