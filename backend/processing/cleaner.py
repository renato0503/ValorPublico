import re
from datetime import datetime, timezone

import pandas as pd

from scraper.models import SENTIMENTO_NEUTRO, RawItem

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_SPACE_RE = re.compile(r"\s+")
_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]",
    flags=re.UNICODE,
)
_LIXO_RE = re.compile(r"[^\w\s.,!?;:%/&+\-@#]", flags=re.UNICODE)


def limpar_texto(texto: str | None) -> str:
    """Remove URLs, emojis, caracteres indesejados e normaliza espacos."""
    if not texto:
        return ""
    t = _URL_RE.sub(" ", texto)
    t = _EMOJI_RE.sub(" ", t)
    t = _LIXO_RE.sub(" ", t)
    t = _SPACE_RE.sub(" ", t)
    return t.strip()


def padronizar_dataframe(itens: list[RawItem]) -> pd.DataFrame:
    """Converte RawItems em DataFrame padronizado, deduplicado e pronto p/ NLP."""
    if not itens:
        return pd.DataFrame(
            columns=[
                "agente_id", "id_externo", "plataforma", "tipo", "texto_limpo",
                "data_publicacao", "autor", "url", "alcance", "metadados",
                "sentimento", "valor_estimado", "created_at",
            ]
        )
    df = pd.DataFrame([i.to_dict() for i in itens])
    df["texto_limpo"] = df["texto_limpo"].map(limpar_texto)
    df = df[df["texto_limpo"].str.len() > 0]
    df = df.drop_duplicates(subset=["agente_id", "id_externo"], keep="first")
    df = df.reset_index(drop=True)
    df["sentimento"] = SENTIMENTO_NEUTRO
    df["valor_estimado"] = 0.0
    df["created_at"] = datetime.now(timezone.utc)
    # Datas ausentes viram NaT no pandas; Firestore nao aceita NaT.
    for col in ("data_publicacao",):
        if col in df.columns:
            df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df