"""Exporta todos os clippings do Firestore para um CSV de auditoria/analise.

Gera `data/export/clippings_YYYYMMDD.csv` com:
  - dados do agente publico (nome, cidade, partido, cargo, votos, etc.);
  - dados do clipping (plataforma, tipo, sentimento, fonte, url, datas);
  - metadados achatados (veiculo, canal, origem, etc.);
  - valoracao (alcance, valor_estimado) e texto limpo.

Uso:
    python scripts/exportar_clippings.py [--saida CAMINHO.csv]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

COLUNAS_BASE = [
    "id_clipping",
    "agente_id",
    "agente_nome_urna",
    "agente_cidade",
    "agente_partido",
    "agente_cargo",
    "agente_genero",
    "agente_legislatura",
    "agente_mandato_ate",
    "agente_votos_2024",
    "plataforma",
    "tipo",
    "sentimento",
    "autor",
    "fonte_veiculo",
    "url",
    "data_publicacao",
    "alcance",
    "valor_estimado",
    "created_at",
    "id_externo",
    "texto_limpo",
]


def _iso(dt) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


def _valor_metadados(val) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return "sim" if val else "nao"
    return str(val)


def exportar(caminho: Path) -> Path:
    db = init_firebase()
    agentes = db.collection(settings.COLLECTION_AGENTES).stream()
    registros: list[dict] = []
    chaves_metadados: set[str] = set()

    total_agentes = 0
    total_clippings = 0
    for doc_agente in agentes:
        agente = doc_agente.to_dict()
        total_agentes += 1
        sub = (
            db.collection(settings.COLLECTION_AGENTES)
            .document(doc_agente.id)
            .collection(settings.SUBCOLLECTION_CLIPPINGS)
        )
        for doc_clip in sub.stream():
            clip = doc_clip.to_dict()
            md = clip.get("metadados") or {}
            chaves_metadados.update(md.keys())
            registros.append(
                {
                    "id_clipping": doc_clip.id,
                    "agente_id": doc_agente.id,
                    "agente_nome_urna": agente.get("nome_urna", ""),
                    "agente_cidade": agente.get("cidade", ""),
                    "agente_partido": agente.get("partido", ""),
                    "agente_cargo": agente.get("cargo", ""),
                    "agente_genero": agente.get("genero", ""),
                    "agente_legislatura": agente.get("legislatura", ""),
                    "agente_mandato_ate": _iso(agente.get("mandato_ate")),
                    "agente_votos_2024": agente.get("votos_2024", ""),
                    "plataforma": clip.get("plataforma", ""),
                    "tipo": clip.get("tipo", ""),
                    "sentimento": clip.get("sentimento", ""),
                    "autor": clip.get("autor", ""),
                    "fonte_veiculo": md.get("veiculo") or clip.get("autor", ""),
                    "url": clip.get("url", ""),
                    "data_publicacao": _iso(clip.get("data_publicacao")),
                    "alcance": clip.get("alcance", 0),
                    "valor_estimado": clip.get("valor_estimado", 0.0),
                    "created_at": _iso(clip.get("created_at")),
                    "id_externo": clip.get("id_externo", ""),
                    "texto_limpo": clip.get("texto_limpo", ""),
                    **{f"md_{k}": _valor_metadados(md.get(k)) for k in chaves_metadados},
                }
            )
            total_clippings += 1

    colunas_md = [f"md_{k}" for k in sorted(chaves_metadados)]
    df = pd.DataFrame(registros, columns=COLUNAS_BASE + colunas_md)
    df = df.sort_values(["agente_id", "data_publicacao"], ascending=[True, False])
    df.to_csv(caminho, index=False, sep=";", encoding="utf-8-sig")
    logger.info(
        "Exportado %d clippings de %d agentes -> %s (colunas metadados: %s)",
        total_clippings, total_agentes, caminho, colunas_md,
    )
    return caminho


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta clippings do Firestore para CSV.")
    parser.add_argument(
        "--saida",
        default="",
        help="Caminho do CSV de saida (padrao: data/export/clippings_YYYYMMDD.csv).",
    )
    args = parser.parse_args()
    if args.saida.strip():
        caminho = Path(args.saida)
    else:
        data = datetime.now().strftime("%Y%m%d")
        caminho = settings.DATA_DIR / "export" / f"clippings_{data}.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    exportar(caminho)


if __name__ == "__main__":
    main()