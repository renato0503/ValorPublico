"""Classifica os comentarios em demandas e grava a colecao `demandas` (E5).

Plano 05 §9 (comentarios), plano 13 (A4 Base / V5 Ouvidoria), plano 14 §2.4.

O que faz:
  1. le os clippings de redes (tipo `Comentario`) dos ultimos N dias;
  2. classifica cada um com `processing/demandas.py` (tema, bairro, urgencia);
  3. grava **so os que sao demanda** em `demandas/{escopo}__{hash}`:
     - id estavel (dedup por texto + agente);
     - status inicial `nova`;
     - proveniencia (rede + URL) e o resumo (sem nome de comentarista no agregado);
  4. recalcula os KPIs K-24..K-27 no `metricas*`.

Uso (a partir de `backend/`):
    python scripts/processar_demandas.py --dias 30
    python scripts/processar_demandas.py --sem-firestore
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.processing.demandas import classificar_demanda
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

STATUS_VALIDOS = {"nova", "andamento", "respondida", "encaminhada"}


def _id_demanda(escopo: str, texto: str) -> str:
    """ID estavel (dedup por escopo + texto normalizado)."""
    digest = hashlib.sha1(texto.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{escopo}__{digest}"


def coletar_comentarios(db, dias: int = 30) -> list[dict]:
    """Comentarios de redes dos clippings (ultimos N dias)."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    saida: list[dict] = []
    for doc in db.collection("agentes_publicos").stream():
        agente = doc.to_dict() or {}
        for clip in doc.reference.collection("clippings").stream():
            dados = clip.to_dict() or {}
            tipo = str(dados.get("tipo", ""))
            # Comentarios e posts publicos podem conter pedido (o classificador
            # decide). Noticias entram so se o texto parecer pedido do cidadao.
            if tipo not in ("Comentario", "Postagem", "Noticia"):
                continue
            bruto = dados.get("data_publicacao")
            if isinstance(bruto, datetime):
                if bruto.tzinfo is None:
                    bruto = bruto.replace(tzinfo=timezone.utc)
                if bruto < limite:
                    continue
            saida.append(
                {
                    "agente_id": doc.id,
                    "casa": agente.get("casa") or agente.get("cidade") or "",
                    "texto": dados.get("texto_limpo", ""),
                    "rede": dados.get("plataforma", ""),
                    "url": dados.get("url", ""),
                    "autor": dados.get("autor", ""),
                    "data": bruto,
                }
            )
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(description="Classifica comentarios em demandas.")
    parser.add_argument("--dias", type=int, default=30)
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    comentarios = coletar_comentarios(db, args.dias)
    logger.info("Comentarios lidos: %d", len(comentarios))

    demandas: list[dict] = []
    vistos: set[str] = set()
    for item in comentarios:
        resultado = classificar_demanda(item["texto"])
        if not resultado["e_demanda"]:
            continue
        escopo = f"agente-{item['agente_id']}"
        ident = _id_demanda(escopo, item["texto"])
        if ident in vistos:
            continue
        vistos.add(ident)
        demandas.append(
            {
                "id": ident,
                "escopo": escopo,
                "casa": item["casa"],
                "agente_id": item["agente_id"],
                "tema": resultado["tema"],
                "bairro": resultado["bairro"],
                "urgencia": resultado["urgencia"],
                "status": "nova",
                "origem": item["rede"] or "comentário",
                "rede": item["rede"],
                "url": item["url"],
                "resumo": resultado["motivo"],
                "texto": item["texto"][:800],
                # O autor fica no bruto; o agregado usa so o resumo (compatibilidade
                # com o padrao dos metricas). Coletado para auditoria do gabinete.
                "autor": item["autor"],
                "criado_em": datetime.now(timezone.utc).isoformat(),
                "data_fonte": item["data"].isoformat() if item["data"] else "",
                "acao_sugerida": resultado["acao_sugerida"],
            }
        )

    logger.info("Demandas classificadas: %d", len(demandas))
    por_tema: dict[str, int] = {}
    por_bairro: dict[str, int] = {}
    por_urgencia: dict[str, int] = {}
    for demanda in demandas:
        por_tema[demanda["tema"]] = por_tema.get(demanda["tema"], 0) + 1
        por_urgencia[demanda["urgencia"]] = por_urgencia.get(demanda["urgencia"], 0) + 1
        if demanda["bairro"]:
            por_bairro[demanda["bairro"]] = por_bairro.get(demanda["bairro"], 0) + 1
    logger.info("Por tema: %s", dict(sorted(por_tema.items(), key=lambda kv: -kv[1])))
    logger.info("Por bairro: %s", dict(sorted(por_bairro.items(), key=lambda kv: -kv[1])[:8]))

    if args.sem_firestore:
        print("Dry-run: demandas classificadas (sem gravar).")
        return 0

    # Grava em lote de 400 (regra da cota).
    lote = db.batch()
    contador = 0
    for demanda in demandas:
        ref = db.collection("demandas").document(demanda["id"])
        lote.set(ref, demanda, merge=True)
        contador += 1
        if contador % 400 == 0:
            lote.commit()
            lote = db.batch()
    if contador % 400:
        lote.commit()
    logger.info("demandas gravadas: %d", contador)

    # KPIs (K-24..K-27) no agregado geral e por escopo.
    agora = datetime.now(timezone.utc).isoformat()
    patch = {
        "demandas": {
            "novas": len(demandas),
            "abertas": len([d for d in demandas if d["status"] != "respondida"]),
            "por_tema": dict(sorted(por_tema.items(), key=lambda kv: -kv[1])),
            "por_bairro": dict(sorted(por_bairro.items(), key=lambda kv: -kv[1])[:40]),
            "por_urgencia": por_urgencia,
            "atualizado_em": agora,
        }
    }
    db.collection("metricas").document("geral").set(patch, merge=True)

    por_escopo: dict[str, list[dict]] = {}
    for demanda in demandas:
        por_escopo.setdefault(demanda["escopo"], []).append(demanda)
    for escopo, itens in por_escopo.items():
        if escopo.startswith("agente-"):
            db.collection("metricas_por_agente").document(escopo[len("agente-"):]).set(
                {
                    "demandas": {
                        "novas": len(itens),
                        "abertas": len([d for d in itens if d["status"] != "respondida"]),
                        "por_tema": _contar(itens, "tema"),
                        "por_bairro": _contar(itens, "bairro"),
                        "por_urgencia": _contar(itens, "urgencia"),
                        "atualizado_em": agora,
                    }
                },
                merge=True,
            )
    logger.info("KPIs de demandas gravados (geral + %d escopos).", len(por_escopo))
    return 0


def _contar(itens: list[dict], campo: str) -> dict:
    contagem: dict[str, int] = {}
    for item in itens:
        chave = item.get(campo) or "—"
        contagem[chave] = contagem.get(chave, 0) + 1
    return dict(sorted(contagem.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "processar_demandas"))
