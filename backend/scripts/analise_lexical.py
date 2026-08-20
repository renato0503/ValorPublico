"""Gera analises lexicais estilo IRAMUTEQ sobre o corpus de clippings.

Uso:
    python scripts/analise_lexical.py [--saida DIR]

Saidas em `backend/data/export/lexical/`:
  - frequencia_global.csv        (palavra, frequencia, percentual)
  - frequencia_por_periodo.csv   (periodo, palavra, frequencia)
  - especificidade.csv           (palavra x periodo: chi2, esperado, sinal)
  - coocorrencia.csv             (termo_a, termo_b, co-ocorrencias)
  - grafo_similaridade.json      (nos + arestas p/ visualizacao)
  - afc_coordenadas.csv          (coordenadas fatoriais de palavras e periodos)
  - chd_classes.csv              (classes, segmentos, palavras caracteristicas)
  - resumo.txt                   (estatisticas gerais do corpus)
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger
from processing import lexical
from processing.nuvem import extrair_palavras

logger = get_logger(__name__)


def carregar_clippings(db) -> list[dict]:
    clippings: list[dict] = []
    for agente in db.collection(settings.COLLECTION_AGENTES).stream():
        for clip in agente.reference.collection(settings.SUBCOLLECTION_CLIPPINGS).stream():
            clippings.append({"agente_id": agente.id, **clip.to_dict()})
    return clippings


def main() -> None:
    parser = argparse.ArgumentParser(description="Analise lexical IRAMUTEQ do corpus.")
    parser.add_argument(
        "--saida", default="",
        help="Diretorio de saida (padrao: data/export/lexical).",
    )
    parser.add_argument(
        "--n-classes", type=int, default=4,
        help="Numero de classes na CHD (padrao 4).",
    )
    args = parser.parse_args()

    saida = Path(args.saida) if args.saida.strip() else settings.DATA_DIR / "export" / "lexical"
    saida.mkdir(parents=True, exist_ok=True)

    db = init_firebase()
    clippings = carregar_clippings(db)
    logger.info("Corpus carregado: %d clippings.", len(clippings))

    # 1) Frequencia global
    freq_global = lexical.frequencia_global(clippings)
    total_palavras = sum(freq_global.values())
    df_global = pd.DataFrame(
        [
            {"palavra": p, "frequencia": f, "percentual": round(100 * f / total_palavras, 3)}
            for p, f in freq_global.items()
        ]
    )
    df_global.to_csv(saida / "frequencia_global.csv", index=False, sep=";", encoding="utf-8-sig")

    # 2) Frequencia por periodo (mes)
    freq_por_mes = lexical.frequencia_por_periodo(clippings)
    linhas_mes = []
    for mes, cont in freq_por_mes.items():
        for palavra, f in cont.items():
            linhas_mes.append({"periodo": mes, "palavra": palavra, "frequencia": f})
    pd.DataFrame(linhas_mes).to_csv(
        saida / "frequencia_por_periodo.csv", index=False, sep=";", encoding="utf-8-sig"
    )

    # 3) Especificidade por periodo
    espec = lexical.especificidade_por_periodo(clippings)
    pd.DataFrame(espec).to_csv(saida / "especificidade.csv", index=False, sep=";", encoding="utf-8-sig")

    # 4) Co-ocorrencia + grafo de similaridade
    grafo = lexical.coocorrencia(clippings)
    df_cooc = pd.DataFrame(grafo["arestas"])
    df_cooc.to_csv(saida / "coocorrencia.csv", index=False, sep=";", encoding="utf-8-sig")
    with open(saida / "grafo_similaridade.json", "w", encoding="utf-8") as f:
        json.dump(grafo, f, ensure_ascii=False, indent=2)

    # 5) AFC (palavra x periodo)
    afc = lexical.analise_correspondencias(clippings)
    linhas_afc = []
    for i, p in enumerate(afc["palavras"]):
        coord = afc["coord_palavras"][i] if i < len(afc["coord_palavras"]) else []
        linhas_afc.append(
            {"tipo": "palavra", "rotulo": p, "eixo1": coord[0] if len(coord) > 0 else 0,
             "eixo2": coord[1] if len(coord) > 1 else 0}
        )
    for i, mes in enumerate(afc["periodos"]):
        coord = afc["coord_periodos"][i] if i < len(afc["coord_periodos"]) else []
        linhas_afc.append(
            {"tipo": "periodo", "rotulo": mes, "eixo1": coord[0] if len(coord) > 0 else 0,
             "eixo2": coord[1] if len(coord) > 1 else 0}
        )
    pd.DataFrame(linhas_afc).to_csv(saida / "afc_coordenadas.csv", index=False, sep=";", encoding="utf-8-sig")

    # 6) CHD (Ward)
    chd_res = lexical.chd(clippings, n_classes=args.n_classes)
    linhas_chd = []
    for cls in chd_res.get("classes", []):
        for p in cls["palavras"]:
            linhas_chd.append(
                {
                    "classe": cls["classe"],
                    "n_segmentos": cls["n_segmentos"],
                    "pct_segmentos": cls["pct"],
                    "palavra": p["palavra"],
                    "chi2": p["chi2"],
                    "frequencia": p["frequencia"],
                }
            )
    pd.DataFrame(linhas_chd).to_csv(saida / "chd_classes.csv", index=False, sep=";", encoding="utf-8-sig")

    # Resumo
    n_palavras = len(freq_global)
    cont_agentes = Counter(c.get("agente_id") for c in clippings)
    resumo = (
        f"Corpus: {len(clippings)} clippings\n"
        f"Agentes: {len(cont_agentes)}\n"
        f"Total de ocorrencias (tokens): {total_palavras}\n"
        f"Vocabulario distinto (types): {n_palavras}\n"
        f"Periodos: {len(freq_por_mes)} meses\n"
        f"Especificidades (chi2>=3.84): {len(espec)}\n"
        f"Arestas de co-ocorrencia: {len(grafo['arestas'])}\n"
        f"CHD: {chd_res.get('segmentos', 0)} segmentos, {len(chd_res.get('classes', []))} classes\n"
    )
    if chd_res.get("aviso"):
        resumo += f"Aviso CHD: {chd_res['aviso']}\n"
    (saida / "resumo.txt").write_text(resumo, encoding="utf-8")

    logger.info("Analise lexical concluida -> %s", saida)
    print(resumo)


if __name__ == "__main__":
    main()