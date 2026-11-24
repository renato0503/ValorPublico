"""Define o orgao de um usuario (separa os dados entre instituicoes).

O campo fica em `usuarios/{uid}.orgao` e e usado pelas `firestore.rules`
para liberar a leitura apenas dos agregados daquele orgao.

Orgaos validos: cuiaba | varzea-grande | almt | governo-mt

Uso:
  python scripts/definir_orgao.py --email fulano@exemplo.com --orgao cuiaba
  python scripts/definir_orgao.py --email chefe@exemplo.com --limpar
  python scripts/definir_orgao.py --uid <uid> --orgao governo-mt
  python scripts/definir_orgao.py --listar

Para o administrador, `--orgao ""` (ou --limpar) significa "ve todos os orgaos".
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from firebase_admin import auth  # noqa: E402

from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

ORGAOS = {
    "cuiaba": "Câmara Municipal de Cuiabá",
    "varzea-grande": "Câmara Municipal de Várzea Grande",
    "almt": "Assembleia Legislativa de MT (ALMT)",
    "governo-mt": "Governo de Mato Grosso",
}


def _uid_de(args) -> str:
    if args.uid:
        return args.uid.strip()
    if args.email:
        usuario = auth.get_user_by_email(args.email.strip().lower())
        return usuario.uid
    raise SystemExit("Informe --uid ou --email (ou use --listar).")


def _listar(db) -> None:
    print("== usuarios ==")
    for doc in db.collection("usuarios").stream():
        x = doc.to_dict() or {}
        print(
            "  %-32s papel=%-8s orgao=%s"
            % (x.get("email", doc.id), x.get("papel", "?"), x.get("orgao") or "-")
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Define o orgao de um usuario.")
    parser.add_argument("--uid", default="")
    parser.add_argument("--email", default="")
    parser.add_argument("--orgao", default=None, choices=list(ORGAOS.keys()))
    parser.add_argument("--limpar", action="store_true", help="Remove o orgao (admin: ve tudo).")
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    db = init_firebase()

    if args.listar:
        _listar(db)
        return

    if args.limpar:
        orgao = ""
    elif args.orgao:
        orgao = args.orgao
    else:
        raise SystemExit("Informe --orgao, --limpar ou --listar.")

    uid = _uid_de(args)
    ref = db.collection("usuarios").document(uid)
    if not ref.get().exists:
        raise SystemExit("Perfil nao encontrado para uid %s." % uid)

    ref.set(
        {"orgao": orgao, "atualizado_em": datetime.now(timezone.utc)},
        merge=True,
    )
    rotulo = ORGAOS.get(orgao, "TODOS (administrador)")
    logger.info("usuarios/%s -> orgao=%s", uid, orgao or "(vazio)")
    print("uid: %s" % uid)
    print("orgao: %s (%s)" % (orgao or "-", rotulo))


if __name__ == "__main__":
    main()
