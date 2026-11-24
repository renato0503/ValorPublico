"""Publica os agregados do clipping do Governo de Mato Grosso (F5).

Grava (com merge=True, em lote de 400):
  * `metricas_por_cidade/governo-de-mato-grosso` -> o Governo do Estado como um todo
  * `metricas_por_casa/governo-mt`             -> a Casa (soma do Executivo)
  * `metricas_por_secretaria/<slug>`          -> uma pasta por secretaria/autarquia
  * `metricas_por_agente/governador-otaviano-pivetta` -> o governador
  * `metricas_por_agente/interino-max-russi`         -> o interino

Reusa o agregador do `atualizar_metricas.py` (mesmo formato do front).
Nao mexe em `metricas/geral` nem nos escopos das Camaras e da ALMT: cada orgao
fica no seu proprio escopo (muralha de dados).

Uso (a partir de `backend/`):
    python scripts/atualizar_metricas_governo.py --jsonl data/governo_mt/noticias-2026-11-24.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from config.settings import BASE_DIR
from scripts.atualizar_metricas import agregar, slugify_cidade

logger = get_logger(__name__)

SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"
PASTA_PADRAO = BASE_DIR / "data" / "governo_mt"


def carregar_itens(caminho: Path) -> list[dict]:
    itens = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        item = json.loads(linha)
        data = item.get("data")
        if isinstance(data, str):
            try:
                data = datetime.fromisoformat(data.replace("Z", "+00:00"))
            except ValueError:
                data = None
        item["data_publicacao"] = data
        itens.append(item)
    return itens


def como_clipping(item: dict) -> dict:
    """Converte o item coletado no formato de clipping esperado pelo agregador."""
    return {
        "id_externo": item.get("url", "")[:120],
        "plataforma": "Web",
        "tipo": "Noticia",
        "texto_limpo": f"{item.get('titulo', '')}\n{item.get('resumo', '')}".strip(),
        "titulo": item.get("titulo", ""),
        "data_publicacao": item.get("data_publicacao"),
        "url": item.get("url", ""),
        "autor": item.get("veiculo", ""),
        "alcance": 0,
        "sentimento": item.get("sentimento", "neutro"),
        "tema": (item.get("temas") or ["geral"])[0],
        "valor_estimado": 0.0,
        "valor_avpe": 0.0,
        "metadados": {
            "veiculo": item.get("veiculo", ""),
            "secretarias": item.get("secretarias", []),
            "siglas": item.get("siglas", []),
            "alvos": item.get("alvos", []),
            "escopo": item.get("escopo", ""),
            "confianca_secretaria": item.get("confianca_secretaria", 0),
            "origem": item.get("origem", ""),
        },
    }


def aplicar_valoracao(db, clippings: list[dict]) -> None:
    """Aplica a valoracao do app (mesma tabela de veiculos e regras do Assessor)."""
    import pandas as pd
    from processing.valoracao import Valorador

    valorador = Valorador(db)
    df = pd.DataFrame(clippings)
    if df.empty:
        return
    df = valorador.aplicar_dataframe(df)
    for indice, linha in df.iterrows():
        clippings[indice]["valor_estimado"] = float(linha.get("valor_estimado") or 0)
        clippings[indice]["valor_avpe"] = float(linha.get("valor_avpe") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agregados do Governo de MT.")
    parser.add_argument("--jsonl", default="")
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    pasta = PASTA_PADRAO
    if args.jsonl:
        arquivo = Path(args.jsonl)
    else:
        arquivos = sorted(pasta.glob("noticias-*.jsonl"))
        if not arquivos:
            logger.error("Nada coletado ainda. Rode coletar_governo_mt.py.")
            return 1
        arquivo = arquivos[-1]

    itens = carregar_itens(arquivo)
    clippings = [como_clipping(i) for i in itens]
    logger.info("Clippings do Governo: %d", len(clippings))

    # por pasta
    por_pasta: dict[str, list[dict]] = defaultdict(list)
    for item, clipping in zip(itens, clippings):
        for sigla in item.get("siglas") or []:
            if sigla:
                por_pasta[sigla].append(clipping)

    # por alvo (governador / interino)
    por_alvo: dict[str, list[dict]] = defaultdict(list)
    for item, clipping in zip(itens, clippings):
        for alvo in item.get("alvos") or []:
            if alvo in ("governador", "interino"):
                por_alvo[alvo].append(clipping)

    if args.sem_firestore:
        print(f"dry-run: {len(clippings)} clippings | {len(por_pasta)} pastas | {len(por_alvo)} alvos")
        for sigla, lista in sorted(por_pasta.items(), key=lambda p: -len(p[1])):
            print(f"  {sigla:16s} {len(lista)}")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    aplicar_valoracao(db, clippings)
    lote = db.batch()
    escritas = 0

    def gravar(colecao: str, doc_id: str, dados: dict) -> None:
        nonlocal lote, escritas
        lote.set(db.collection(colecao).document(doc_id), dados, merge=True)
        escritas += 1
        if escritas % 400 == 0:
            lote.commit()
            lote = db.batch()

    agora = datetime.now(timezone.utc).isoformat()

    # 1) o Governo do Estado como um todo (cidade) + a Casa
    agregado = agregar(clippings)
    agregado["atualizado_em"] = agora
    agregado["escopo"] = "governo-estado"
    agregado["orgao"] = "governo-mt"
    gravar("metricas_por_cidade", slugify_cidade("Governo de Mato Grosso"), agregado)
    gravar("metricas_por_casa", "governo-mt", agregado)

    # 2) uma pasta por secretaria/autarquia
    nomes = {
        s["sigla"]: s.get("nome", "")
        for s in seed.get("secretarias", []) + seed.get("autarquias", [])
    }
    titulares = {
        s["sigla"]: s.get("titular", "")
        for s in seed.get("secretarias", []) + seed.get("autarquias", [])
    }
    for sigla, lista in por_pasta.items():
        pasta_doc = agregar(lista)
        pasta_doc["atualizado_em"] = agora
        pasta_doc["orgao"] = "governo-mt"
        pasta_doc["pasta"] = {
            "sigla": sigla,
            "nome": nomes.get(sigla, sigla),
            "titular": titulares.get(sigla, ""),
        }
        gravar("metricas_por_secretaria", _slug(sigla), pasta_doc)

    # 3) governador e interino
    slugs_alvo = {
        "governador": seed.get("governador", {}).get("slug", "governador-otaviano-pivetta"),
        "interino": seed.get("interino", {}).get("slug", "interino-max-russi"),
    }
    for alvo, lista in por_alvo.items():
        doc = agregar(lista)
        doc["atualizado_em"] = agora
        doc["orgao"] = "governo-mt"
        gravar("metricas_por_agente", slugs_alvo[alvo], doc)

    if escritas % 400:
        lote.commit()

    logger.info("Documentos gravados: %d", escritas)
    logger.info(
        "  metricas_por_cidade/governo-de-mato-grosso · metricas_por_casa/governo-mt · "
        "metricas_por_secretaria/* (%d) · metricas_por_agente/%s",
        len(por_pasta),
        ", ".join(slugs_alvo.values()),
    )
    return 0


def _slug(texto: str) -> str:
    import re
    import unicodedata

    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8").lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "atualizar_metricas_governo"))
