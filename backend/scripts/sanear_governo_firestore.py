"""Saneia os clippings do Governo de MT já gravados no Firestore (plano 22, S0).

* apaga os clippings de veículos de fora de MT (Assembleia, Polícia Civil,
  Bombeiros de MS...), que o agregador trouxe por causa de "Mato Grosso";
* limpa entidades HTML / ``nbsp`` em ``titulo`` e ``texto_limpo``.

Por padrão só mostra o que faria. Para gravar: ``--aplicar``.

Uso (a partir de ``backend/``):
    python scripts/sanear_governo_firestore.py
    python scripts/sanear_governo_firestore.py --aplicar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from processing.governo_filtros import limpar_texto, titulo_so_de_ms, veiculo_fora_de_mt  # noqa: E402

LOTE = 400


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aplicar", action="store_true", help="grava no Firestore")
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    colecao = db.collection("agentes_publicos").document("governo-mt").collection("clippings")

    apagar, limpar = [], []
    total = 0
    for doc in colecao.stream():
        total += 1
        dados = doc.to_dict() or {}
        veiculo = (dados.get("metadados") or {}).get("veiculo") or dados.get("autor") or ""
        if veiculo_fora_de_mt(veiculo) or titulo_so_de_ms(dados.get("titulo")):
            apagar.append((doc.reference, veiculo, dados.get("titulo", "")))
            continue
        mudancas = {}
        for campo in ("titulo", "texto_limpo"):
            valor = dados.get(campo) or ""
            if "nbsp" in valor.lower() or "&" in valor:
                limpo = limpar_texto(valor) if campo == "titulo" else "\n".join(
                    limpar_texto(linha) for linha in valor.split("\n")
                )
                if limpo != valor:
                    mudancas[campo] = limpo
        if mudancas:
            limpar.append((doc.reference, mudancas))

    print(f"clippings do Governo: {total}")
    print(f"  de fora de MT (apagar): {len(apagar)}")
    for _, veiculo, titulo in apagar[:60]:
        print(f"    - {veiculo[:40]:40s} | {titulo[:70]}")
    print(f"  com entidade HTML (limpar): {len(limpar)}")

    if not args.aplicar:
        print("\nnada gravado (use --aplicar)")
        return 0

    lote, n = db.batch(), 0
    for ref, _, _ in apagar:
        lote.delete(ref)
        n += 1
        if n % LOTE == 0:
            lote.commit()
            lote = db.batch()
    for ref, mudancas in limpar:
        lote.update(ref, mudancas)
        n += 1
        if n % LOTE == 0:
            lote.commit()
            lote = db.batch()
    if n % LOTE:
        lote.commit()
    print(f"\ngravado: {len(apagar)} apagados, {len(limpar)} limpos")
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "sanear_governo_firestore"))
