"""Testes do guard de projeto da credencial do Firebase (achado A1).

Uso: python backend/tests/teste_firebase_guard.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import FIREBASE_PROJECT_ID, FIREBASE_SERVICE_ACCOUNT
from core.firebase_client import _validar_projeto

ok = 0
falhas = []


def checa(nome, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  PASS  {nome}")
    else:
        falhas.append(nome)
        print(f"  FAIL  {nome} {extra}")


def _credencial(projeto: str) -> Path:
    fh = tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump({"type": "service_account", "project_id": projeto}, fh)
    fh.close()
    return Path(fh.name)


def _levanta(fn, *args):
    try:
        fn(*args)
    except RuntimeError as exc:
        return str(exc)
    return ""


print("== guard de projeto ==")
checa(
    "caminho da credencial resolvido (absoluto, backend/serviceAccountKey.json)",
    Path(FIREBASE_SERVICE_ACCOUNT).is_absolute()
    and Path(FIREBASE_SERVICE_ACCOUNT).name == "serviceAccountKey.json",
    FIREBASE_SERVICE_ACCOUNT,
)

certo = _credencial(FIREBASE_PROJECT_ID)
_validar_projeto(certo, FIREBASE_PROJECT_ID)
checa("credencial do projeto certo passa", True)

errado = _credencial("projeto-errado-teste")
msg = _levanta(_validar_projeto, errado, FIREBASE_PROJECT_ID)
checa("credencial de outro projeto aborta", "projeto-errado-teste" in msg, msg)

msg_vazio = _levanta(_validar_projeto, errado, "")
checa("sem FIREBASE_PROJECT_ID nao aborta (guarda desativada)", msg_vazio == "", msg_vazio)

print(f"\nRESULTADO: {ok} passaram, {len(falhas)} falharam")
sys.exit(1 if falhas else 0)
