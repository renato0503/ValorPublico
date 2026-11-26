"""Publica o clipping do Governo de MT no Firestore (ValorPublico).

Grava as notícias coletadas como clippings da entidade `governo-mt`
(subcoleção `clippings`) e depois chama os agregados
(`atualizar_metricas_governo.py`), para que o painel mostre:
  * metricas_por_cidade/governo-de-mato-grosso  (o Governo como um todo)
  * metricas_por_casa/governo-mt
  * metricas_por_secretaria/<slug>  (uma pasta por secretaria/autarquia)
  * metricas_por_agente/governador-otaviano-pivetta e interim-max-russi

Regras:
  * escrita em lote de 400 (cota do Spark) e `merge=True` (idempotente);
  * guarda o bruto **so** no escopo do Governo (muralha de dados);
  * 429 -> sai com codigo 75 (tentar no proximo ciclo).

Uso (a partir de `backend/`):
    python scripts/publicar_governo_mt.py --dry-run
    python scripts/publicar_governo_mt.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from config.settings import BASE_DIR
from processing.governo_filtros import linhas_da_base, sanear_itens

logger = get_logger(__name__)

SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"
PASTA_PADRAO = BASE_DIR / "data" / "governo_mt"
LOTE = 400


def carregar(caminho: Path | None) -> list[dict]:
    """Base do Governo (um arquivo ou a uniao de todos), saneada."""
    itens = []
    for item in linhas_da_base(PASTA_PADRAO, caminho):
        data = item.get("data")
        if isinstance(data, str):
            try:
                item["data"] = datetime.fromisoformat(data.replace("Z", "+00:00"))
            except ValueError:
                item["data"] = None
        itens.append(item)
    itens, removidos = sanear_itens(itens)
    if removidos:
        logger.info("Ignorados %d itens de veiculos de fora de MT", len(removidos))
    return itens


def id_do_clipping(item: dict) -> str:
    base = item.get("url") or item.get("titulo") or ""
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def documento(item: dict, valores: dict | None = None) -> dict:
    valores = valores or {}
    return {
        "id_externo": id_do_clipping(item),
        "titulo": item.get("titulo", ""),
        "texto_limpo": f"{item.get('titulo', '')}\n{item.get('resumo', '')}".strip(),
        "plataforma": "Web",
        "tipo": "Noticia",
        "data_publicacao": item.get("data"),
        "url": item.get("url", ""),
        "autor": item.get("veiculo", ""),
        "alcance": 0,
        "sentimento": item.get("sentimento", "neutro"),
        "tema": (item.get("temas") or ["geral"])[0],
        "categorias": item.get("temas") or [],
        "secretarias": item.get("secretarias", []),
        "siglas": item.get("siglas", []),
        "municipios": item.get("municipios", []),
        "alvos": item.get("alvos", []),
        "escopo": item.get("escopo", ""),
        "confianca_secretaria": item.get("confianca_secretaria", 0),
        "motivo_secretaria": item.get("motivo_secretaria", {}),
        "origem_coleta": item.get("origem", ""),
        "valor_estimado": float(valores.get("valor_estimado") or 0),
        "valor_avpe": float(valores.get("valor_avpe") or 0),
        "metadados": {
            "veiculo": item.get("veiculo", ""),
            "secretarias": item.get("secretarias", []),
            "siglas": item.get("siglas", []),
            "alvos": item.get("alvos", []),
            "escopo": item.get("escopo", ""),
            "origem": item.get("origem", ""),
        },
    }


def valorar(db, itens: list[dict]) -> list[dict]:
    """Aplica a tabela de mídia/AVPE aos itens do Governo (fallback 400/Web)."""
    try:
        from scripts.atualizar_metricas_governo import aplicar_valoracao, como_clipping

        base = []
        for item in itens:
            copia = dict(item)
            copia["data_publicacao"] = item.get("data")
            base.append(como_clipping(copia))
        aplicar_valoracao(db, base)
        return base
    except Exception as exc:  # noqa: BLE001
        logger.warning("Valoracao indisponivel (%s); gravando valor 0.", str(exc)[:120])
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica o clipping do Governo de MT.")
    parser.add_argument("--jsonl", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sem-agregados", action="store_true")
    args = parser.parse_args()

    arquivo = Path(args.jsonl) if args.jsonl else None
    itens = carregar(arquivo)
    if not itens:
        logger.error("Nada coletado. Rode coletar_governo_mt.py.")
        return 1
    logger.info("Publicando %d notícias do Governo de MT...", len(itens))

    if args.dry_run:
        print(f"dry-run: {len(itens)} clippings em agentes_publicos/governo-mt/clippings")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    valores = valorar(db, itens)
    if valores:
        total_valor = sum(float(v.get("valor_estimado") or 0) for v in valores)
        logger.info("Valoracao aplicada: R$ %.2f no total.", total_valor)
    colecao = db.collection("agentes_publicos").document("governo-mt").collection("clippings")
    lote = db.batch()
    total = 0
    for indice, item in enumerate(itens):
        valor = valores[indice] if indice < len(valores) else None
        lote.set(colecao.document(id_do_clipping(item)), documento(item, valor), merge=True)
        total += 1
        if total % LOTE == 0:
            lote.commit()
            lote = db.batch()
    if total % LOTE:
        lote.commit()
    logger.info("Clippings publicados: %d", total)

    if not args.sem_agregados:
        from scripts import atualizar_metricas_governo

        argv = sys.argv[:]
        sys.argv = [sys.argv[0]]
        if args.jsonl:
            sys.argv += ["--jsonl", str(arquivo)]
        try:
            codigo = atualizar_metricas_governo.main()
        finally:
            sys.argv = argv
        if codigo:
            return codigo

    logger.info("Publicação do Governo de MT concluída.")
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "publicar_governo_mt"))
