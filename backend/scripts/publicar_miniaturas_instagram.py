"""Miniaturas dos posts do Instagram oficial do Governo (plano 22).

Gera uma miniatura WebP (lado maior 360 px) de cada post já coletado em
`docs/instagram` (capa baixada ou print manual) e grava tudo em
`imagens_governo/instagram` como base64. Sem Firebase Storage; o documento é
legível só pelo Governo (regra em firestore.rules).

Uso (a partir de backend/):
    python scripts/publicar_miniaturas_instagram.py --sem-firestore
    python scripts/publicar_miniaturas_instagram.py
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parents[2]
PASTA = ROOT / "docs" / "instagram"
ARQUIVOS = {
    "@govmatogrosso": PASTA / "ingestao_govmt.jsonl",
    "@otavianopivetta": PASTA / "ingestao_governador.jsonl",
}
LADO = 360
LIMITE_DOC = 950_000


def _imagem_do_post(registro: dict) -> Path | None:
    id_externo = str(registro.get("id_externo") or "")
    candidatos = [PASTA / id_externo / "capa.png", PASTA / id_externo / "pagina.png"]
    for midia in registro.get("midia") or []:
        local = str(midia.get("arquivo_local") or "").replace("\\", "/")
        if local:
            candidatos.append(ROOT / "docs" / local)
    plano = (registro.get("metadados") or {}).get("foto_flat")
    if plano:
        candidatos.append(PASTA / f"{plano}.png")
    return next((c for c in candidatos if c.exists()), None)


def _miniatura(caminho: Path, qualidade: int) -> str:
    from PIL import Image

    with Image.open(caminho) as img:
        img = img.convert("RGB")
        img.thumbnail((LADO, LADO))
        saida = io.BytesIO()
        img.save(saida, "WEBP", quality=qualidade, method=6)
    return base64.b64encode(saida.getvalue()).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    posts = []
    for conta, arquivo in ARQUIVOS.items():
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            registro = json.loads(linha)
            if registro.get("tipo") != "Postagem":
                continue
            caminho = _imagem_do_post(registro)
            posts.append((conta, str(registro.get("id_externo")), caminho))

    for qualidade in (62, 50, 40):
        miniaturas = {}
        for conta, id_externo, caminho in posts:
            if caminho:
                miniaturas[id_externo] = {"thumb": _miniatura(caminho, qualidade), "conta": conta}
        tamanho = sum(len(m["thumb"]) for m in miniaturas.values())
        if tamanho < LIMITE_DOC:
            break
    sem = [i for _, i, c in posts if not c]
    print(f"posts: {len(posts)} | com miniatura: {len(miniaturas)} | sem imagem: {sem} | {tamanho // 1024} KB (qualidade {qualidade})")
    if args.sem_firestore:
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    db.collection("imagens_governo").document("instagram").set(
        {
            "orgao": "governo-mt",
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
            "miniaturas": miniaturas,
        }
    )
    print("gravado em imagens_governo/instagram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
