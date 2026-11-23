"""Exporta a Camada DSM (radar, alertas e cobertura) para CSV.

Complementa `exportar_clippings.py`: gera arquivos de auditoria que respondem
as perguntas que o cliente faz sobre o servico:

  radar_publico.csv    publicacoes oficiais (orgao, tipo, simbolos, link)
  alertas.csv          alertas acionaveis (nivel, tipo, fonte, acao sugerida)
  cobertura.csv        SLA e cobertura por veiculo/tier de cada escopo

Uso:
    python scripts/exportar_camada_dsm.py
    python scripts/exportar_camada_dsm.py --saida-dir data/export
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.quota import main_com_cota  # noqa: E402

logger = get_logger(__name__)


def _iso(valor) -> str:
    if not valor:
        return ""
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)[:19]


def exportar_radar(db, saida: Path) -> int:
    """Publicacoes oficiais ingeridas (colecao radar_publico)."""
    registros = []
    for doc in db.collection("radar_publico").stream():
        dados = doc.to_dict() or {}
        registros.append({
            "id": doc.id,
            "orgao": dados.get("orgao", ""),
            "tipo": dados.get("tipo", ""),
            "classe": dados.get("classe", ""),
            "classe_semantica": dados.get("classe_semantica", ""),
            "cidade": dados.get("cidade", ""),
            "simbolos_publicos": "sim" if dados.get("simbolos_publicos") else "",
            "veiculo": (dados.get("metadados") or {}).get("veiculo", ""),
            "titulo": (dados.get("texto_limpo") or "")[:300],
            "url": dados.get("url", ""),
            "data_publicacao": _iso(dados.get("data_publicacao")),
            "coletado_em": _iso(dados.get("created_at")),
        })
    registros.sort(key=lambda r: r["coletado_em"], reverse=True)
    caminho = saida / "radar_publico.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(registros[0].keys()) if registros else ["id"])
        writer.writeheader()
        writer.writerows(registros)
    logger.info("Radar exportado: %d itens -> %s", len(registros), caminho)
    return len(registros)


def exportar_alertas(db, saida: Path) -> int:
    """Alertas acionaveis publicados por escopo."""
    registros = []
    for doc in db.collection("alertas").stream():
        dados = doc.to_dict() or {}
        escopo = dados.get("escopo") or {}
        for chave, bloco in dados.items():
            if not chave.startswith("periodo-"):
                continue
            for alerta in ((bloco.get("alertas") or {}).get("itens") or []):
                registros.append({
                    "escopo": escopo.get("chave", doc.id),
                    "escopo_nome": escopo.get("nome", ""),
                    "periodo": chave.replace("periodo-", ""),
                    "chave": alerta.get("chave", ""),
                    "nivel": alerta.get("nivel", ""),
                    "tipo": alerta.get("tipo", ""),
                    "titulo": alerta.get("titulo", ""),
                    "detalhe": (alerta.get("detalhe") or "")[:400],
                    "acao_sugerida": alerta.get("acao_sugerida", ""),
                    "veiculo": alerta.get("veiculo", ""),
                    "url": alerta.get("url", ""),
                    "data_publicacao": _iso(alerta.get("data_publicacao")),
                    "valor_estimado": alerta.get("valor_estimado", 0.0),
                    "criado_em": _iso(alerta.get("criado_em")),
                })
    caminho = saida / "alertas.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        campos = list(registros[0].keys()) if registros else ["escopo"]
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)
    logger.info("Alertas exportados: %d itens -> %s", len(registros), caminho)
    return len(registros)


def exportar_cobertura(db, saida: Path) -> int:
    """SLA e cobertura por veiculo/tier."""
    registros = []
    for doc in db.collection("cobertura").stream():
        dados = doc.to_dict() or {}
        escopo = dados.get("escopo") or {}
        for chave, bloco in dados.items():
            if not chave.startswith("periodo-"):
                continue
            cob = bloco.get("cobertura") or {}
            for veiculo, info in (cob.get("por_veiculo") or {}).items():
                registros.append({
                    "escopo": escopo.get("chave", doc.id),
                    "escopo_nome": escopo.get("nome", ""),
                    "periodo": chave.replace("periodo-", ""),
                    "veiculo": veiculo,
                    "tier": info.get("tier", ""),
                    "itens": info.get("itens", 0),
                    "sla_medio_min": info.get("sla_medio", 0.0),
                })
    caminho = saida / "cobertura.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        campos = list(registros[0].keys()) if registros else ["escopo"]
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)
    logger.info("Cobertura exportada: %d linhas -> %s", len(registros), caminho)
    return len(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta a Camada DSM para CSV.")
    parser.add_argument("--saida-dir", default="", help="Diretorio de saida (padrao: data/export).")
    args = parser.parse_args()

    from config import settings

    saida = Path(args.saida_dir) if args.saida_dir.strip() else settings.DATA_DIR / "export"
    saida.mkdir(parents=True, exist_ok=True)

    db = init_firebase()
    radar = exportar_radar(db, saida)
    alertas = exportar_alertas(db, saida)
    cobertura = exportar_cobertura(db, saida)
    logger.info(
        "Camada DSM exportada (%s): radar=%d alertas=%d cobertura=%d",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), radar, alertas, cobertura,
    )


if __name__ == "__main__":
    main_com_cota(main, "exportar_camada_dsm")
