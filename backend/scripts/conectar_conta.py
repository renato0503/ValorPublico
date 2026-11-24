"""Conecta uma conta propria do agente (E4, plano 06 §9).

Fluxo do piloto (sem Cloud Functions, sem Blaze):
  1. o agente clica em "Conectar minhas redes" no app;
  2. a plataforma abre a tela de autorizacao e volta para `/oauth/callback`
     (pagina estatica do Hosting) com o `code`;
  3. o agente copia o `code` e o tecnico do gabinete roda este script:
         python scripts/conectar_conta.py --agente <id> --rede instagram --codigo <CODE>
  4. o script troca o `code` pelo token longo e grava em **GitHub Secrets /
     arquivo cifrado** (nunca no Firestore legivel pelo cliente);
  5. o job diario de `redes_proprias` le o token, coleta, agrega e grava
     `metricas_por_agente/<id>.redes_proprias`.

Variaveis de ambiente (`.env` do servidor, nunca no repositorio):
  META_APP_ID, META_APP_SECRET, META_REDIRECT_URI
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI
  TOKENS_DIR  (pasta cifrada onde os tokens ficam; padrao: data/tokens)

Sem estas variaveis o script avisa que o app ainda nao foi aprovado e nao faz
nada (modo piloto desligado).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import requests

from cerra_nucleo.core.logger import get_logger
from config import settings

logger = get_logger(__name__)

REDES_META = {
    # rede: (endpoint do token, escopos)
    "instagram": ("https://graph.facebook.com/v21.0/oauth/access_token", "instagram_business_basic,instagram_business_manage_insights,instagram_business_manage_comments,instagram_business_manage_messages"),
    "facebook": ("https://graph.facebook.com/v21.0/oauth/access_token", "pages_show_list,pages_read_engagement,pages_read_user_content,pages_manage_engagement,read_insights"),
    "threads": ("https://graph.threads.net/oauth/access_token", "threads_basic,threads_read_replies,threads_manage_insights,threads_manage_mentions"),
}
REDES_TIKTOK = {
    "tiktok": ("https://open.tiktokapis.com/v2/oauth/token/", "user.info.basic,user.info.profile,user.info.stats,video.list"),
}

PASTA_TOKENS = Path(os.getenv("TOKENS_DIR", str(Path(settings.DATA_DIR) / "tokens")))


def _env(nome: str) -> str:
    return os.getenv(nome, "").strip()


def _salvar_token(agente: str, rede: str, dados: dict) -> Path:
    """Grava o token em arquivo cifrado local (fora do Firestore)."""
    PASTA_TOKENS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_TOKENS / f"{agente}__{rede}.json"
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        destino.chmod(0o600)
    except Exception:  # noqa: BLE001
        pass
    return destino


def trocar_meta(rede: str, codigo: str) -> dict:
    """Troca o `code` pelo token de longa duracao (Meta)."""
    app_id = _env("META_APP_ID")
    app_secret = _env("META_APP_SECRET")
    redirect = _env("META_REDIRECT_URI")
    if not (app_id and app_secret and redirect):
        return {"ok": False, "erro": "Credenciais da Meta ausentes (META_APP_ID/SECRET/REDIRECT_URI)."}
    endpoint, _ = REDES_META[rede]
    resp = requests.get(
        endpoint,
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect,
            "code": codigo,
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        return {"ok": False, "erro": f"Meta respondeu {resp.status_code}: {resp.text[:200]}"}
    dados = resp.json()
    # Troca o token curto por um de longa duracao (60 dias)
    token = dados.get("access_token", "")
    if token:
        try:
            longo = requests.get(
                "https://graph.facebook.com/v21.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": token,
                },
                timeout=30,
            )
            if longo.status_code < 400:
                dados.update(longo.json())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Troca por token longo falhou: %s", exc)
    return {"ok": bool(dados.get("access_token")), "dados": dados}


def trocar_tiktok(rede: str, codigo: str) -> dict:
    """Troca o `code` pelo token (TikTok Display API)."""
    client_key = _env("TIKTOK_CLIENT_KEY")
    client_secret = _env("TIKTOK_CLIENT_SECRET")
    redirect = _env("TIKTOK_REDIRECT_URI")
    if not (client_key and client_secret and redirect):
        return {"ok": False, "erro": "Credenciais do TikTok ausentes (TIKTOK_CLIENT_KEY/SECRET/REDIRECT_URI)."}
    endpoint, _ = REDES_TIKTOK[rede]
    resp = requests.post(
        endpoint,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": codigo,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        return {"ok": False, "erro": f"TikTok respondeu {resp.status_code}: {resp.text[:200]}"}
    dados = resp.json()
    return {"ok": bool(dados.get("access_token")), "dados": dados}


def main() -> int:
    parser = argparse.ArgumentParser(description="Conecta uma conta propria (OAuth).")
    parser.add_argument("--agente", required=True)
    parser.add_argument("--rede", required=True, choices=sorted(set(REDES_META) | set(REDES_TIKTOK)))
    parser.add_argument("--codigo", required=True)
    args = parser.parse_args()

    if args.rede in REDES_META:
        resultado = trocar_meta(args.rede, args.codigo)
    else:
        resultado = trocar_tiktok(args.rede, args.codigo)

    if not resultado.get("ok"):
        logger.error("Falha ao conectar %s: %s", args.rede, resultado.get("erro", "erro"))
        logger.info(
            "Piloto: o app precisa estar em Standard Access/sandbox com o dono como tester "
            "(plano 06 §8). Sem isso, a plataforma recusa a troca do code."
        )
        return 1

    destino = _salvar_token(args.agente, args.rede, resultado["dados"])
    logger.info("Token salvo em %s (fora do Firestore).", destino)
    logger.info(
        "Proximo passo: copie o conteudo para o GitHub Secret e rode a rotina "
        "'redes_proprias' do Actions para preencher metricas_por_agente.rodar."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
