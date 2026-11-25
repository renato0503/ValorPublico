"""Reclassifica o sentimento de clippings já gravados.

Usa o léxico de domínio + VADER de `processing/sentiment.py`, sem re-coletar.
Atualiza apenas o campo `sentimento` com merge, em lotes de 400.

Uso (a partir de backend/):
    python scripts/reclassificar_sentimento.py --dry-run
    python scripts/reclassificar_sentimento.py --orgao governo-mt
    python scripts/reclassificar_sentimento.py --todos --limite 500
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger
from core.quota import main_com_cota
from processing.sentiment import AnalisadorSentimento

logger = get_logger(__name__)
LOTE = 400


def _agente_pertence(agente: dict, orgao: str) -> bool:
    if not orgao:
        return True
    return str(agente.get("orgao") or "") == orgao


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclassifica sentimento de clippings.")
    parser.add_argument("--orgao", default="governo-mt", help="Filtra clippings pelo órgão do agente.")
    parser.add_argument("--todos", action="store_true", help="Processa todos os órgãos.")
    parser.add_argument("--incluir-comentarios", action="store_true", help="Inclui tipo Comentario.")
    parser.add_argument("--limite", type=int, default=None, help="Teto de clippings para teste.")
    parser.add_argument("--dry-run", action="store_true", help="Não grava; só mostra contagens e amostras.")
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    analisador = AnalisadorSentimento()
    orgao = "" if args.todos else args.orgao
    processados = 0
    alterados = 0
    antigos = Counter()
    novos = Counter()
    amostras = []
    lote = []

    def flush() -> None:
        nonlocal lote
        if lote and not args.dry_run:
            batch = db.batch()
            for ref, valor in lote:
                batch.update(ref, {"sentimento": valor})
            batch.commit()
            lote = []

    for agente_ref in db.collection("agentes_publicos").stream():
        agente = agente_ref.to_dict() or {}
        if not _agente_pertence(agente, orgao):
            continue
        for clip_ref in agente_ref.reference.collection("clippings").stream():
            if args.limite and processados >= args.limite:
                break
            dados = clip_ref.to_dict() or {}
            tipo = str(dados.get("tipo") or "")
            if tipo == "Comentario" and not args.incluir_comentarios:
                continue
            texto = str(dados.get("texto_limpo") or "")
            if not texto.strip():
                continue
            antigo = str(dados.get("sentimento") or "neutro")
            novo = analisador.classificar(texto)
            processados += 1
            antigos[antigo] += 1
            novos[novo] += 1
            if antigo != novo:
                alterados += 1
                lote.append((clip_ref.reference, novo))
                if len(amostras) < 12:
                    amostras.append((antigo, novo, texto.replace("\n", " ")[:140]))
                if len(lote) >= LOTE:
                    flush()
        if args.limite and processados >= args.limite:
            break

    flush()
    print(f"Processados: {processados} | alterados: {alterados}")
    print(f"Antes: {dict(antigos)}")
    print(f"Depois: {dict(novos)}")
    if amostras:
        print("Amostras:")
        for antigo, novo, texto in amostras:
            print(f"  {antigo} -> {novo}: {texto}")
    if args.dry_run:
        print("Dry-run: nada foi gravado.")
    return 0


if __name__ == "__main__":
    main_com_cota(main, "reclassificar_sentimento")

