"""Carrega no Firestore os conteúdos do Instagram já coletados.

Não re-coleta nada e não usa credenciais do Instagram. Lê o JSONL de
`docs/instagram/`, passa pelo pipeline normal (`RawItem` -> cleaner ->
enriquecimento -> FirestoreRepo) e grava de forma idempotente em
`agentes_publicos/<agente_id>/clippings/Instagram_<id_externo>`.

Uso (a partir de backend/):
    python scripts/carregar_instagram_valorpublico.py --dry-run
    python scripts/carregar_instagram_valorpublico.py --agente governo-mt
    python scripts/carregar_instagram_valorpublico.py --agente governador-otaviano-pivetta
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger
from core.quota import main_com_cota
from processing.cleaner import padronizar_dataframe
from processing.enriquecimento import enriquecer_dataframe
from scraper.models import (
    PLATAFORMA_INSTAGRAM,
    TIPO_COMENTARIO,
    TIPO_POSTAGEM,
    RawItem,
)

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ARQUIVO_PADRAO = ROOT / "docs" / "instagram" / "ingestao_valorpublico.jsonl"
ARQUIVOS_AGENTE = {
    "governo-mt": ROOT / "docs" / "instagram" / "ingestao_govmt.jsonl",
    "governador-otaviano-pivetta": ROOT / "docs" / "instagram" / "ingestao_governador.jsonl",
}


def _data_iso(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    texto = str(valor).strip().replace("Z", "+00:00")
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        logger.warning("Data inválida ignorada: %r", valor)
        return None
    return data if data.tzinfo else data.replace(tzinfo=timezone.utc)


def _raw_item(registro: dict) -> RawItem:
    tipo = registro.get("tipo") or TIPO_POSTAGEM
    return RawItem(
        agente_id=str(registro.get("agente_id") or ""),
        id_externo=str(registro.get("id_externo") or ""),
        plataforma=str(registro.get("plataforma") or PLATAFORMA_INSTAGRAM),
        tipo=tipo,
        texto_limpo=str(registro.get("texto_limpo") or ""),
        data_publicacao=_data_iso(registro.get("data_publicacao")),
        autor=str(registro.get("autor") or ""),
        url=str(registro.get("url") or ""),
        alcance=int(registro.get("alcance") or 0),
        metadados=registro.get("metadados") or {},
        midia=registro.get("midia") or [],
    )


def _ler_jsonl(caminho: Path, agente: str | None, limite: int | None) -> list[dict]:
    if not caminho.exists():
        raise SystemExit(f"Arquivo não encontrado: {caminho}")
    registros: list[dict] = []
    with caminho.open("r", encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                item = json.loads(linha)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"JSON inválido em {caminho}:{numero}: {exc}") from exc
            if agente and item.get("agente_id") != agente:
                continue
            registros.append(item)
            if limite and len(registros) >= limite:
                break
    return registros


def _resumo(df, brutos: Counter) -> dict:
    limpos = Counter(df["tipo"].tolist()) if not df.empty else Counter()
    return {
        "brutos": dict(brutos),
        "limpos": dict(limpos),
        "descartados": sum(brutos.values()) - len(df),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Carrega Instagram coletado no Firestore.")
    parser.add_argument("--arquivo", type=Path, default=None, help="JSONL de entrada")
    parser.add_argument(
        "--agente",
        choices=sorted(ARQUIVOS_AGENTE),
        help="Usa o JSONL já separado desse agente.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Valida e mostra contagens sem gravar.")
    parser.add_argument("--limite", type=int, default=None, help="Limite de registros para teste.")
    args = parser.parse_args()

    caminho = args.arquivo or (ARQUIVOS_AGENTE[args.agente] if args.agente else ARQUIVO_PADRAO)
    registros = _ler_jsonl(caminho, args.agente, args.limite)
    if not registros:
        raise SystemExit("Nenhum registro encontrado.")

    por_agente: dict[str, list[dict]] = defaultdict(list)
    for registro in registros:
        agente_id = str(registro.get("agente_id") or "")
        if not agente_id or not registro.get("id_externo"):
            logger.warning("Registro sem agente/id_externo ignorado.")
            continue
        por_agente[agente_id].append(registro)

    logger.info("%s: %d registros lidos.", caminho, len(registros))
    resultados = {}

    if args.dry_run:
        for agente_id, itens in por_agente.items():
            brutos = Counter(str(r.get("tipo") or TIPO_POSTAGEM) for r in itens)
            df = padronizar_dataframe([_raw_item(r) for r in itens])
            resultados[agente_id] = _resumo(df, brutos)
        for agente_id, resumo in resultados.items():
            limpos = sum(resumo["limpos"].values())
            print(
                f"{agente_id}: brutos={sum(resumo['brutos'].values())} "
                f"({resumo['brutos'].get(TIPO_POSTAGEM, 0)} Postagem + "
                f"{resumo['brutos'].get(TIPO_COMENTARIO, 0)} Comentario) "
                f"limpos={limpos} "
                f"descartados={resumo['descartados']} "
                f"por_tipo={resumo['limpos']}"
            )
        print("Dry-run: nada foi gravado.")
        return 0

    from core.firebase_client import init_firebase
    from storage.firestore_repo import FirestoreRepo

    db = init_firebase()
    repo = FirestoreRepo(db)

    for agente_id, itens in por_agente.items():
        agente_snap = db.collection("agentes_publicos").document(agente_id).get()
        if not agente_snap.exists:
            raise SystemExit(
                f"Agente {agente_id} não existe em agentes_publicos. "
                "Rode backend/scripts/seed_governo_mt.py antes."
            )
        agente = {**agente_snap.to_dict(), "id": agente_id}
        brutos = Counter(str(r.get("tipo") or TIPO_POSTAGEM) for r in itens)
        df = padronizar_dataframe([_raw_item(r) for r in itens])
        descartados = len(itens) - len(df)
        df = enriquecer_dataframe(df, agente=agente)
        gravados = repo.salvar_lote(df)
        resultados[agente_id] = {
            "brutos": dict(brutos),
            "limpos": dict(Counter(df["tipo"].tolist())) if not df.empty else {},
            "descartados": descartados,
            "gravados": gravados,
        }
        logger.info("%s: %d gravados, %d descartados.", agente_id, gravados, descartados)

    print("\nResumo da carga:")
    for agente_id, resumo in resultados.items():
        print(
            f"- {agente_id}: gravados={resumo['gravados']} descartados={resumo['descartados']} "
            f"por_tipo={resumo['limpos']}"
        )
    return 0


if __name__ == "__main__":
    main_com_cota(main, "carregar_instagram_valorpublico")
