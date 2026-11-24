"""Publica as Firestore Rules usando a service account (Rules API).

Por que nao o CLI: nesta conta o `firebase deploy --only firestore:rules`
retorna 403 (documentado no STATUS §6), e o login do CLI expira. A Rules API
resolve direto com a credencial de servico.

Uso (a partir de `backend/`):
    python scripts/publicar_regras.py            # publica firestore.rules
    python scripts/publicar_regras.py --dry-run  # so mostra o que faria

Requer que a service account tenha papel de Firebase Admin/Editor.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

ESCOPO = ["https://www.googleapis.com/auth/cloud-platform"]
BASE = "https://firebaserules.googleapis.com/v1"
ARQUIVO_REGRAS = Path(__file__).resolve().parent.parent.parent / "firestore.rules"
NOME_RELEASE = "cloud.firestore"


def _token() -> str:
    cred = service_account.Credentials.from_service_account_file(
        settings.FIREBASE_SERVICE_ACCOUNT, scopes=ESCOPO
    )
    cred.refresh(Request())
    return cred.token


def publicar(conteudo: str, projeto: str, token: str) -> dict:
    """Cria um ruleset novo e aponta o release do Firestore para ele."""
    cabecalho = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1) cria o ruleset
    resp = requests.post(
        f"{BASE}/projects/{projeto}/rulesets",
        headers=cabecalho,
        json={"source": {"files": [{"name": "firestore.rules", "content": conteudo}]}},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"criar ruleset: {resp.status_code} {resp.text[:300]}")
    nome_ruleset = resp.json().get("name", "")
    logger.info("Ruleset criado: %s", nome_ruleset)

    # 2) aponta o release do Firestore para o ruleset novo
    release = f"projects/{projeto}/releases/{NOME_RELEASE}"
    resp2 = requests.patch(
        f"{BASE}/{release}",
        headers=cabecalho,
        json={"release": {"name": release, "rulesetName": nome_ruleset}},
        timeout=60,
    )
    if resp2.status_code >= 400:
        raise RuntimeError(f"atualizar release: {resp2.status_code} {resp2.text[:300]}")
    return {"ruleset": nome_ruleset, "release": release, "projeto": projeto}


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica as Firestore Rules via Rules API.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arquivo", default=str(ARQUIVO_REGRAS))
    args = parser.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.exists():
        logger.error("Arquivo de regras nao encontrado: %s", caminho)
        return 1
    conteudo = caminho.read_text(encoding="utf-8").replace("\r\n", "\n")
    projeto = settings.FIREBASE_PROJECT_ID
    logger.info("Projeto: %s | regras: %s (%d chars)", projeto, caminho.name, len(conteudo))

    if args.dry_run:
        print(f"[dry-run] publicaria {caminho.name} em {projeto} ({len(conteudo)} chars)")
        return 0

    resultado = publicar(conteudo, projeto, _token())
    logger.info("Regras publicadas em %s (%s)", projeto, resultado["ruleset"])
    print(f"OK: regras de {projeto} publicadas ({resultado['ruleset']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
