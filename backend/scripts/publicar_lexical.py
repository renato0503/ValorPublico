"""Publica as analises lexicais (IRAMUTEQ) no Firestore para o dashboard.

Le os arquivos gerados por `scripts/analise_lexical.py` em
`backend/data/export/lexical/` e grava na colecao `analise_lexical`:

  - `analise_lexical/afc`     -> mapa fatorial (palavras + periodos x eixo1/eixo2)
  - `analise_lexical/chd`     -> classes tematicas (segmentos, pct, palavras chi2)
  - `analise_lexical/grafo`   -> grafo de similaridade (nos + arestas)
  - `analise_lexical/resumo`  -> estatisticas gerais do corpus

O grafo e podado para as `--top-arestas` (padrao 80) mais fortes, mantendo o
dashboard responsivo sem perder as relacoes principais.

Uso: python scripts/publicar_lexical.py [--origem DIR] [--top-arestas 80]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

COLLECTION_LEXICAL = "analise_lexical"
MAX_AFC_PALAVRAS = 120


def _ler_csv(origem: Path, nome: str) -> pd.DataFrame:
    caminho = origem / nome
    if not caminho.exists():
        logger.warning("Arquivo lexical ausente: %s", caminho)
        return pd.DataFrame()
    return pd.read_csv(caminho, sep=";", encoding="utf-8-sig")


def _doc_afc(origem: Path) -> dict:
    df = _ler_csv(origem, "afc_coordenadas.csv")
    if df.empty:
        return {"palavras": [], "periodos": [], "aviso": "AFC ainda nao gerado."}
    palavras = df[df["tipo"] == "palavra"].head(MAX_AFC_PALAVRAS)
    periodos = df[df["tipo"] == "periodo"]
    return {
        "palavras": [
            {"rotulo": str(r["rotulo"]), "eixo1": float(r["eixo1"]), "eixo2": float(r["eixo2"])}
            for _, r in palavras.iterrows()
        ],
        "periodos": [
            {"rotulo": str(r["rotulo"]), "eixo1": float(r["eixo1"]), "eixo2": float(r["eixo2"])}
            for _, r in periodos.iterrows()
        ],
    }


def _doc_chd(origem: Path) -> dict:
    df = _ler_csv(origem, "chd_classes.csv")
    if df.empty:
        return {"classes": [], "aviso": "CHD ainda nao gerada."}
    classes: dict[int, dict] = {}
    for _, r in df.iterrows():
        cls = int(r["classe"])
        entrada = classes.setdefault(
            cls,
            {"classe": cls, "n_segmentos": int(r["n_segmentos"]),
             "pct_segmentos": round(float(r["pct_segmentos"]), 1), "palavras": []},
        )
        entrada["palavras"].append(
            {
                "palavra": str(r["palavra"]),
                "chi2": round(float(r["chi2"]), 1),
                "frequencia": int(r["frequencia"]),
            }
        )
    return {"classes": list(classes.values())}


def _doc_grafo(origem: Path, top_arestas: int) -> dict:
    caminho = origem / "grafo_similaridade.json"
    if not caminho.exists():
        return {"nos": [], "arestas": [], "aviso": "Grafo ainda nao gerado."}
    with open(caminho, encoding="utf-8") as f:
        grafo = json.load(f)

    arestas = sorted(grafo.get("arestas", []), key=lambda a: a.get("peso", 0), reverse=True)
    arestas_podadas = arestas[:top_arestas]
    ids = {n.get("id") for a in arestas_podadas for n in ({"id": a["a"]}, {"id": a["b"]})}
    nos = [n for n in grafo.get("nos", []) if n.get("id") in ids]
    return {"nos": nos, "arestas": arestas_podadas}


def _doc_dendrograma(origem: Path) -> dict:
    caminho = origem / "dendrograma.json"
    if not caminho.exists():
        return {"polilinhas": [], "aviso": "Dendrograma ainda nao gerado."}
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _doc_resumo(origem: Path) -> dict:
    resumo_path = origem / "resumo.txt"
    if not resumo_path.exists():
        return {"texto": ""}
    return {"texto": resumo_path.read_text(encoding="utf-8")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica analises lexicais no Firestore.")
    parser.add_argument("--origem", default="", help="Diretorio de origem (padrao: data/export/lexical).")
    parser.add_argument("--top-arestas", type=int, default=80, help="Arestas mais fortes a publicar.")
    args = parser.parse_args()

    origem = Path(args.origem) if args.origem.strip() else settings.DATA_DIR / "export" / "lexical"
    db = init_firebase()
    agora = datetime.now(timezone.utc)

    docs = {
        "afc": _doc_afc(origem),
        "chd": _doc_chd(origem),
        "grafo": _doc_grafo(origem, args.top_arestas),
        "dendrograma": _doc_dendrograma(origem),
        "resumo": _doc_resumo(origem),
    }
    batch = db.batch()
    for doc_id, dados in docs.items():
        dados["gerado_em"] = agora
        batch.set(db.collection(COLLECTION_LEXICAL).document(doc_id), dados, merge=True)
    batch.commit()

    n_arestas = len(docs["grafo"]["arestas"])
    n_classes = len(docs["chd"]["classes"])
    n_palavras_afc = len(docs["afc"]["palavras"])
    n_ramos = len(docs["dendrograma"]["polilinhas"])
    logger.info(
        "Analise lexical publicada em %s: AFC(%d palavras) + CHD(%d classes) + grafo(%d arestas) + dendrograma(%d ramos).",
        COLLECTION_LEXICAL, n_palavras_afc, n_classes, n_arestas, n_ramos,
    )


if __name__ == "__main__":
    main()