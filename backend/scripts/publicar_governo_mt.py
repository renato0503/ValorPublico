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

logger = get_logger(__name__)

SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"
PASTA_PADRAO = BASE_DIR / "data" / "governo_mt"
LOTE = 400


def carregar(caminho: Path) -> list[dict]:
    itens = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            item = json.loads(linha)
            data = item.get("data")
            if isinstance(data, str):
                try:
                    item["data"] = datetime.fromisoformat(data.replace("Z", "+00:00"))
                except ValueError:
                    item["data"] = None
            itens.append(item)
    return itens


def id_do_clipping(item: dict) -> str:
    base = item.get("url") or item.get("titulo") or ""
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def documento(item: dict) -> dict:
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
        "alvos": item.get("alvos", []),
        "escopo": item.get("escopo", ""),
        "confianca_secretaria": item.get("confianca_secretaria", 0),
        "motivo_secretaria": item.get("motivo_secretaria", {}),
        "origem_coleta": item.get("origem", ""),
        "metadados": {
            "veiculo": item.get("veiculo", ""),
            "secretarias": item.get("secretarias", []),
            "siglas": item.get("siglas", []),
            "alvos": item.get("alvos", []),
            "escopo": item.get("escopo", ""),
            "origem": item.get("origem", ""),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica o clipping do Governo de MT.")
    parser.add_argument("--jsonl", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sem-agregados", action="store_true")
    args = parser.parse_args()

    pasta = PASTA_PADRAO
    if args.jsonl:
        arquivo = Path(args.jsonl)
    else:
        arquivos = sorted(pasta.glob("noticias-*.jsonl"))
        if not arquivos:
            logger.error("Nada coletado. Rode coletar_governo_mt.py.")
            return 1
        arquivo = arquivos[-1]

    itens = carregar(arquivo)
    logger.info("Publicando %d notícias do Governo de MT...", len(itens))

    if args.dry_run:
        print(f"dry-run: {len(itens)} clippings em agentes_publicos/governo-mt/clippings")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    colecao = db.collection("agentes_publicos").document("governo-mt").collection("clippings")
    lote = db.batch()
    total = 0
    for item in itens:
        lote.set(colecao.document(id_do_clipping(item)), documento(item), merge=True)
        total += 1
        if total % LOTE == 0:
            lote.commit()
            lote = db.batch()
    if total % LOTE:
        lote.commit()
    logger.info("Clippings publicados: %d", total)

    if not args.sem_agregados:
        from scripts import atualizar_metricas_governo

        codigo = atualizar_metricas_governo.main()
        if codigo:
            return codigo

    logger.info("Publicação do Governo de MT concluída.")
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "publicar_governo_mt"))
