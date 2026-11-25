"""Testes de integridade dos dados do ValorPúblico/Instagram.

Uso:
    python scripts/testar_integridade_valorpublico.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase


def main() -> int:
    db = init_firebase()
    falhas: list[str] = []
    ok: list[str] = []

    agentes = {
        "governo-mt": "governo-mt",
        "governador-otaviano-pivetta": "governador-otaviano-pivetta",
    }
    for agente_id in agentes:
        doc = db.collection("agentes_publicos").document(agente_id).get()
        if not doc.exists:
            falhas.append(f"agente ausente: {agente_id}")
        else:
            ok.append(f"agente presente: {agente_id}")

    casa = db.collection("metricas_por_casa").document("governo-mt").get()
    dados = casa.to_dict() if casa.exists else {}
    if not casa.exists:
        falhas.append("metricas_por_casa/governo-mt ausente")
    else:
        ok.append("metricas_por_casa/governo-mt presente")

    posts = (dados.get("redes_sociais") or {}).get("posts") or []
    if len(posts) < 20:
        falhas.append(f"redes_sociais.posts insuficiente: {len(posts)}")
    else:
        ok.append(f"redes_sociais.posts: {len(posts)}")
    total_comentarios = sum(len(p.get("comentarios") or []) for p in posts)
    if posts and total_comentarios == 0:
        falhas.append("posts sem comentários agregados")
    else:
        ok.append(f"comentários nos posts: {total_comentarios}")

    galeria = (dados.get("imagens") or {}).get("galeria") or []
    if not galeria:
        falhas.append("galeria de imagens vazia em metricas_por_casa")
    else:
        ok.append(f"galeria de imagens: {len(galeria)}")
    ids_posts = {str(p.get("post_shortcode") or p.get("id_externo")) for p in posts}
    ids_galeria = {str(g.get("post_shortcode") or g.get("id_externo")) for g in galeria}
    sem_vinculo = ids_galeria - ids_posts
    if sem_vinculo:
        falhas.append(f"imagens sem post correspondente: {sorted(sem_vinculo)[:5]}")
    else:
        ok.append("imagens vinculadas aos posts")

    if (dados.get("imagens") or {}).get("kpis", {}).get("k70_postos_com_imagem", 0) <= 0:
        falhas.append("k70_postos_com_imagem não calculado")
    else:
        ok.append("K-70 de imagens preenchido")

    tend = dados.get("tendencias") or {}
    if len(tend.get("em_alta_mt") or []) < 5:
        falhas.append("tendências em alta em MT insuficientes")
    else:
        ok.append(f"tendências MT: {len(tend.get('em_alta_mt') or [])}")
    if not dados.get("previsao"):
        falhas.append("previsão ausente em metricas_por_casa")
    else:
        ok.append("previsão presente")

    for agente_id in agentes:
        col = db.collection("agentes_publicos").document(agente_id).collection("clippings")
        docs = list(col.stream())
        instagram = [d for d in docs if d.id.startswith("Instagram_")]
        if not instagram:
            falhas.append(f"sem clippings Instagram em {agente_id}")
            continue
        ids = [d.id for d in instagram]
        if len(ids) != len(set(ids)):
            falhas.append(f"ids Instagram duplicados em {agente_id}")
        datas_ok = 0
        midia_ok = 0
        for d in instagram:
            x = d.to_dict() or {}
            data = x.get("data_publicacao")
            if data is None or isinstance(data, datetime) or hasattr(data, "to_datetime"):
                datas_ok += 1
            if x.get("midia"):
                midia_ok += 1
        if datas_ok != len(instagram):
            falhas.append(f"data_publicacao inválida em {agente_id}: {len(instagram)-datas_ok}")
        if midia_ok == 0:
            falhas.append(f"midia vazia nos posts de {agente_id}")
        ok.append(f"{agente_id}: {len(instagram)} Instagram · {midia_ok} com mídia")

    print("\n=== Integridade ValorPúblico ===")
    for linha in ok:
        print("  OK  ", linha)
    for linha in falhas:
        print("  FALHA", linha)
    print(f"\nResumo: {len(ok)} OK, {len(falhas)} falhas.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
