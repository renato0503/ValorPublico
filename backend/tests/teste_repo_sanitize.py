"""Testes da sanitizacao de tipos antes de gravar no Firestore (achado A6).

Uso: python backend/tests/teste_repo_sanitize.py
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.firestore_repo import FirestoreRepo

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


s = FirestoreRepo._sanitizar

print("== sanitizacao de valores do pandas/numpy ==")
checa("NaT vira None", s(pd.NaT) is None)
checa("NaN vira None", s(float("nan")) is None)
checa("np.nan vira None", s(np.float64("nan")) is None)
checa("np.int64 vira int", s(np.int64(7)) == 7 and type(s(np.int64(7))) is int)
checa("np.bool_ vira bool", s(np.bool_(True)) is True)

ts = pd.Timestamp("2026-10-19 12:00:00")
conv = s(ts)
checa("Timestamp vira datetime com timezone", isinstance(conv, datetime) and conv.tzinfo is not None)

ingenuo = datetime(2026, 10, 19, 12, 0)
checa("datetime ingenuo recebe UTC", s(ingenuo).tzinfo == timezone.utc)
checa("date vira datetime UTC", s(date(2026, 10, 19)).tzinfo == timezone.utc)

aninhado = {
    "data_publicacao": pd.NaT,
    "metadados": {"n": np.int64(3), "tags": [np.float64("nan"), "ok"]},
}
limpo = s(aninhado)
checa("dict aninhado sem NaT/NaN",
      limpo["data_publicacao"] is None
      and limpo["metadados"]["n"] == 3
      and limpo["metadados"]["tags"] == [None, "ok"],
      limpo)
checa("texto preservado", s("manchete") == "manchete")

print(f"\nRESULTADO: {ok} passaram, {len(falhas)} falharam")
sys.exit(1 if falhas else 0)
