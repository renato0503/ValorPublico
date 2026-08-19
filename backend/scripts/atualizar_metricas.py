"""Recalcula metricas agregadas do dashboard e grava no Firestore.

Produz documentos otimizados para leitura em tempo real no PWA:
  metricas/geral               -> visao global (KPIs + series + top fontes)
  metricas_por_cidade/<slug>   -> visao por cidade
  metricas_por_agente/<id>     -> visao por parlamentar

Uso: python backend/scripts/atualizar_metricas.py
"""

import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unicodedata import normalize

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import COLLECTION_AGENTES, SUBCOLLECTION_CLIPPINGS
from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

CATEGORIA_REDES = {"Twitter", "Instagram", "Facebook"}
CATEGORIA_WEB = {"Web"}


def slugify_cidade(cidade: str) -> str:
    cidade = normalize("NFKD", cidade).encode("ascii", "ignore").decode("utf-8")
    return "-".join(cidade.strip().lower().split())


def _chave_dia(dt) -> str:
    if dt is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).date().isoformat()
    return str(dt)[:10]


def _categoria(plataforma: str) -> str:
    if plataforma in CATEGORIA_REDES:
        return "Redes Sociais"
    if plataforma in CATEGORIA_WEB:
        return "Web"
    return plataforma


def coletar_clippings(db) -> list[dict]:
    clippings = []
    agentes = db.collection(COLLECTION_AGENTES).stream()
    for agente in agentes:
        cidade = agente.to_dict().get("cidade", "")
        for clip in agente.reference.collection(SUBCOLLECTION_CLIPPINGS).stream():
            clippings.append({"agente_id": agente.id, "cidade": cidade, **clip.to_dict()})
    return clippings


def agregar(clippings: list[dict]) -> dict:
    """Metricas de um conjunto de clippings (global, cidade ou agente)."""
    veiculos: Counter = Counter()
    audiencia_por_veiculo: defaultdict[str, int] = defaultdict(int)
    valor_por_veiculo: defaultdict[str, float] = defaultdict(float)
    categorias: Counter = Counter()
    sentimentos: Counter = Counter()
    valoracao_por_plataforma: defaultdict[str, float] = defaultdict(float)
    valoracao_por_categoria: defaultdict[str, float] = defaultdict(float)
    serie: defaultdict[str, Counter] = defaultdict(Counter)

    for c in clippings:
        plataforma = c.get("plataforma", "Web")
        autor = (c.get("autor") or "").strip()
        veiculo = c.get("metadados", {}).get("veiculo") or autor or "Sem fonte"
        valor = float(c.get("valor_estimado") or 0)

        categorias[_categoria(plataforma)] += 1
        sentimentos[c.get("sentimento", "neutro")] += 1
        valoracao_por_plataforma[plataforma] += valor
        valoracao_por_categoria[_categoria(plataforma)] += valor

        veiculos[veiculo] += 1
        audiencia_por_veiculo[veiculo] += int(c.get("alcance") or 0)
        valor_por_veiculo[veiculo] += valor

        dia = _chave_dia(c.get("data_publicacao"))
        serie[dia][plataforma] += 1

    top_veiculos = []
    for nome, qtd in veiculos.most_common(10):
        top_veiculos.append(
            {
                "nome": nome,
                "clippings": qtd,
                "audiencia": audiencia_por_veiculo[nome],
                "valor_estimado": round(valor_por_veiculo[nome], 2),
            }
        )

    return {
        "total_clippings": len(clippings),
        "total_veiculos": len(veiculos),
        "audiencia_total": sum(audiencia_por_veiculo.values()),
        "valoracao_total": round(sum(valor_por_veiculo.values()), 2),
        "distribuicao_categorias": dict(categorias),
        "distribuicao_sentimento": dict(sentimentos),
        "valoracao_por_plataforma": dict(valoracao_por_plataforma),
        "valoracao_por_categoria": dict(valoracao_por_categoria),
        "top_veiculos": top_veiculos,
        "dias": {dia: dict(contagens) for dia, contagens in sorted(serie.items())},
        "atualizado_em": datetime.now(timezone.utc),
    }


def main() -> None:
    db = init_firebase()
    clippings = coletar_clippings(db)
    logger.info("Lidos %d clippings de todas as subcolecoes.", len(clippings))

    db.collection("metricas").document("geral").set(agregar(clippings), merge=True)

    por_cidade: dict[str, list[dict]] = defaultdict(list)
    por_agente: dict[str, list[dict]] = defaultdict(list)
    for c in clippings:
        cidade = c.get("cidade") or "Sem cidade"
        por_cidade[cidade].append(c)
        por_agente[c["agente_id"]].append(c)

    for cidade, clips in por_cidade.items():
        db.collection("metricas_por_cidade").document(slugify_cidade(cidade)).set(
            agregar(clips), merge=True
        )
    for agente_id, clips in por_agente.items():
        db.collection("metricas_por_agente").document(agente_id).set(
            agregar(clips), merge=True
        )

    logger.info(
        "Metricas gravadas: geral + %d cidades + %d agentes. Total de clippings: %d.",
        len(por_cidade), len(por_agente), len(clippings),
    )


if __name__ == "__main__":
    main()