"""Coleta as contas proprias conectadas (E4, plano 06 §1/§9).

Le os tokens (arquivo local cifrado, nunca no Firestore) e preenche
`metricas_por_agente/<id>.redes_proprias`:

    redes_proprias: {
      conectadas: ["instagram", ...], atualizado_em,
      instagram: {seguidores, alcance_7d, views_7d, engajamento_7d, comentarios_7d, top_posts[]},
      facebook/threads/youtube/tiktok: ...,
      comentarios: {total, sentimento{}, temas[], recentes[]}
    }

Modo piloto: sem token, o script apenas avisa (nao falha). Ao desconectar, apaga
os dados daquela conta (exigencia da Meta/TikTok e da LGPD).

Uso (a partir de `backend/`):
    python scripts/coletar_redes_proprias.py --agente adevair-cabral
    python scripts/coletar_redes_proprias.py --todos
    python scripts/coletar_redes_proprias.py --agente X --desconectar instagram
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import requests

from cerra_nucleo.core.logger import get_logger
from config import settings

logger = get_logger(__name__)

PASTA_TOKENS = Path(os.getenv("TOKENS_DIR", str(Path(settings.DATA_DIR) / "tokens")))
GRAPH = "https://graph.facebook.com/v21.0"
TIKTOK_API = "https://open.tiktokapis.com/v2"


def tokens_do_agente(agente: str) -> dict[str, dict]:
    """Le os tokens conectados de um agente."""
    saida: dict[str, dict] = {}
    if not PASTA_TOKENS.exists():
        return saida
    for arquivo in PASTA_TOKENS.glob(f"{agente}__*.json"):
        rede = arquivo.stem.split("__", 1)[1]
        try:
            saida[rede] = json.loads(arquivo.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Token ilegivel %s: %s", arquivo.name, exc)
    return saida


def _get_json(url: str, params: dict) -> dict:
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code >= 400:
            return {"erro": f"{resp.status_code}: {resp.text[:120]}"}
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"erro": str(exc)[:120]}


def coletar_instagram(token: str) -> dict:
    """Perfil, midias e insights do Instagram (conta propria)."""
    perfil = _get_json(
        f"{GRAPH}/me",
        {"fields": "id,username,followers_count,follows_count,media_count", "access_token": token},
    )
    if "erro" in perfil:
        return perfil
    midias = _get_json(
        f"{GRAPH}/{perfil.get('id')}/media",
        {
            "fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count",
            "limit": 12,
            "access_token": token,
        },
    )
    return {
        "seguidores": int(perfil.get("followers_count") or 0),
        "publicacoes": int(perfil.get("media_count") or 0),
        "top_posts": [
            {
                "id": m.get("id"),
                "legenda": (m.get("caption") or "")[:160],
                "curtidas": int(m.get("like_count") or 0),
                "comentarios": int(m.get("comments_count") or 0),
                "url": m.get("permalink", ""),
                "data": m.get("timestamp", ""),
            }
            for m in (midias.get("data") or [])[:5]
        ],
    }


def coletar_facebook(token: str) -> dict:
    """Pagina do Facebook (conta propria)."""
    paginas = _get_json(f"{GRAPH}/me/accounts", {"access_token": token})
    if "erro" in paginas or not paginas.get("data"):
        return {"erro": "sem pagina vinculada"}
    pagina = paginas["data"][0]
    token_pagina = pagina.get("access_token", token)
    dados = _get_json(
        f"{GRAPH}/{pagina.get('id')}",
        {"fields": "name,fan_count,followers_count,posts.limit(5){message,created_time,permalink_url}", "access_token": token_pagina},
    )
    return {
        "seguidores": int(dados.get("followers_count") or dados.get("fan_count") or 0),
        "top_posts": [
            {
                "legenda": (p.get("message") or "")[:160],
                "url": p.get("permalink_url", ""),
                "data": p.get("created_time", ""),
            }
            for p in ((dados.get("posts") or {}).get("data") or [])
        ],
    }


def coletar_threads(token: str) -> dict:
    """Perfil e posts do Threads (conta propria)."""
    perfil = _get_json(
        "https://graph.threads.net/v1.0/me",
        {"fields": "id,username,threads_profile_picture_url", "access_token": token},
    )
    if "erro" in perfil:
        return perfil
    return {"seguidores": 0, "perfil": perfil.get("username", ""), "top_posts": []}


def coletar_tiktok(token: str) -> dict:
    """Perfil e videos do TikTok (Display API)."""
    try:
        resp = requests.get(
            f"{TIKTOK_API}/user/info/",
            params={"fields": "open_id,union_id,avatar_url,display_name,follower_count,following_count,likes_count,video_count"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code >= 400:
            return {"erro": f"{resp.status_code}: {resp.text[:120]}"}
        usuario = (resp.json().get("data") or {}).get("user") or {}
        return {
            "seguidores": int(usuario.get("follower_count") or 0),
            "curtidas_total": int(usuario.get("likes_count") or 0),
            "videos": int(usuario.get("video_count") or 0),
            "top_posts": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {"erro": str(exc)[:120]}


COLETORES = {
    "instagram": coletar_instagram,
    "facebook": coletar_facebook,
    "threads": coletar_threads,
    "tiktok": coletar_tiktok,
}


def coletar_agente(agente: str) -> dict:
    """Monta o agregado `redes_proprias` do agente."""
    tokens = tokens_do_agente(agente)
    agregado: dict = {
        "conectadas": sorted(tokens),
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "comentarios": {"total": 0, "sentimento": {}, "temas": [], "recentes": []},
    }
    for rede, dados in tokens.items():
        coletor = COLETORES.get(rede)
        if not coletor:
            continue
        token = dados.get("access_token") or dados.get("token") or ""
        if not token:
            continue
        resultado = coletor(token)
        agregado[rede] = resultado
        if "erro" in resultado:
            logger.warning("%s/%s: %s", agente, rede, resultado["erro"])
    return agregado


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta contas proprias conectadas.")
    parser.add_argument("--agente", default="")
    parser.add_argument("--todos", action="store_true")
    parser.add_argument("--desconectar", default="", help="rede a desconectar (apaga os dados)")
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    if not PASTA_TOKENS.exists() or not any(PASTA_TOKENS.glob("*.json")):
        logger.info(
            "Nenhuma conta conectada. Modo piloto: o app da Meta/TikTok precisa ser aprovado "
            "e o agente precisa autorizar (scripts/conectar_conta.py)."
        )
        return 0

    if args.desconectar:
        alvo = PASTA_TOKENS / f"{args.agente}__{args.desconectar}.json"
        if alvo.exists():
            alvo.unlink()
            logger.info("Token de %s removido; dados da conta serao apagados.", args.desconectar)
            if not args.sem_firestore:
                from core.firebase_client import init_firebase

                db = init_firebase()
                db.collection("metricas_por_agente").document(args.agente).set(
                    {"redes_proprias": {args.desconectar: None, "conectadas": []}}, merge=True
                )
        return 0

    agentes = []
    if args.todos:
        agentes = [p.stem.split("__")[0] for p in PASTA_TOKENS.glob("*__*.json")]
    elif args.agente:
        agentes = [args.agente]
    else:
        logger.error("Informe --agente ou --todos.")
        return 2

    db = None
    if not args.sem_firestore:
        from core.firebase_client import init_firebase

        db = init_firebase()

    for agente in sorted(set(agentes)):
        agregado = coletar_agente(agente)
        conectadas = agregado.get("conectadas", [])
        logger.info("%s: %s", agente, ", ".join(conectadas) or "sem contas")
        if db is not None and conectadas:
            db.collection("metricas_por_agente").document(agente).set(
                {"redes_proprias": agregado}, merge=True
            )
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "redes_proprias"))
