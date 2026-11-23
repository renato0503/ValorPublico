"""Cria um usuario do painel (Firebase Auth + perfil em `usuarios/{uid}`).

Faz as duas etapas numa chamada so:
  1. cria (ou reaproveita) o usuario no Firebase Authentication (E-mail/Senha);
  2. grava `usuarios/<uid>` com o escopo que as `firestore.rules` usam.

Perfil gravado:
  {email, papel, agente_id, agente_ids[], chaves[], nome, criado_em}
  - agente_id  : id do agente (ex.: "fulano-de-tal")
  - agente_ids : ids de agentes que o usuario pode ver
  - chaves     : chaves de escopo da Camada DSM ("geral", "agente-<id>")

Uso:
  python scripts/criar_usuario.py --email fulano@exemplo.com --papel agente \
      --agente-id fulano-de-tal
  python scripts/criar_usuario.py --email chefe@exemplo.com --papel admin --geral

Sem --senha, uma senha aleatoria e gerada e impressa uma unica vez.
"""

import argparse
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from firebase_admin import auth  # noqa: E402

from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

PAPEIS = ("agente", "assessor", "admin", "owner")


def _senha_aleatoria(tamanho: int = 16) -> str:
    alfabeto = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*"
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def _obter_ou_criar(email: str, senha: str, nome: str):
    try:
        usuario = auth.get_user_by_email(email)
        logger.info("Usuario ja existia no Auth: %s (%s).", email, usuario.uid)
        return usuario, False
    except auth.UserNotFoundError:
        usuario = auth.create_user(email=email, password=senha, display_name=nome or None)
        logger.info("Usuario criado no Auth: %s (%s).", email, usuario.uid)
        return usuario, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria usuario do painel (Auth + perfil).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--senha", default="", help="Sem valor, gera uma senha aleatoria.")
    parser.add_argument("--nome", default="")
    parser.add_argument("--papel", default="agente", choices=PAPEIS)
    parser.add_argument("--agente-id", default="", help="Ex.: fulano-de-tal")
    parser.add_argument(
        "--agente-ids",
        default="",
        help="Lista separada por virgula (padrao: o proprio --agente-id).",
    )
    parser.add_argument(
        "--chaves",
        default="",
        help="Escopos DSM separados por virgula (padrao: agente-<id>).",
    )
    parser.add_argument("--geral", action="store_true", help="Da acesso ao escopo geral.")
    args = parser.parse_args()

    email = args.email.strip().lower()
    agente_id = (args.agente_id or "").strip()
    agente_ids = [a.strip() for a in args.agente_ids.split(",") if a.strip()]
    if not agente_ids and agente_id:
        agente_ids = [agente_id]
    chaves = [c.strip() for c in args.chaves.split(",") if c.strip()]
    if not chaves:
        chaves = [f"agente-{a}" for a in agente_ids]
    if args.geral:
        chaves.append("geral")

    senha = args.senha or _senha_aleatoria()
    db = init_firebase()
    usuario, criado = _obter_ou_criar(email, senha, args.nome)

    perfil = {
        "email": email,
        "nome": args.nome or usuario.display_name or "",
        "papel": args.papel,
        "agente_id": agente_id,
        "agente_ids": agente_ids,
        "chaves": sorted(set(chaves)),
        "atualizado_em": datetime.now(timezone.utc),
        "criado_em": datetime.now(timezone.utc),
    }
    db.collection("usuarios").document(usuario.uid).set(perfil, merge=True)
    logger.info("Perfil gravado em usuarios/%s (chaves=%s).", usuario.uid, perfil["chaves"])

    print(f"uid: {usuario.uid}")
    print(f"email: {email}")
    if criado and not args.senha:
        print(f"senha inicial (troque no primeiro acesso): {senha}")


if __name__ == "__main__":
    main()
