import pandas as pd
import vaderSentiment.vaderSentiment as vader_mod
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from core.logger import get_logger
from scraper.models import (
    SENTIMENTO_NEGATIVO,
    SENTIMENTO_NEUTRO,
    SENTIMENTO_POSITIVO,
)

logger = get_logger(__name__)

# Léxico em português para complementar o VADER (treinado em inglês)
_LEXICO_POSITIVO = {
    "aprova": 3.0, "aprovado": 3.0, "bom": 2.5, "ótimo": 3.0, "otimo": 3.0,
    "excelente": 3.5, "brilhante": 3.5, "parabéns": 3.0, "parabens": 3.0,
    "venceu": 3.0, "vitória": 3.0, "vitoria": 3.0, "conquista": 2.5,
    "premiado": 3.0, "honra": 2.0, "reconhecimento": 2.5, "merece": 2.5,
    "transparente": 2.0, "dedicado": 2.5, "trabalhador": 2.0, "compromisso": 1.5,
    "qualidade": 2.0, "avanço": 2.0, "avanco": 2.0, "melhoria": 2.0,
    "apoio": 1.5, "gratidão": 3.0, "gratidao": 3.0, "obrigado": 2.0,
    "obrigada": 2.0, "lindo": 2.0, "linda": 2.0, "maravilha": 3.0,
}
_LEXICO_NEGATIVO = {
    "reprova": -3.0, "reprovado": -3.0, "péssimo": -3.0, "pessimo": -3.0,
    "horrível": -3.0, "horrivel": -3.0, "terrível": -3.0, "terrivel": -3.0,
    "corrupto": -3.0, "corrupção": -3.0, "corrupcao": -3.0, "vergonha": -3.0,
    "incompetente": -3.0, "incompetência": -3.0, "incompetencia": -3.0,
    "frustração": -2.5, "frustracao": -2.5, "decepção": -2.5, "decepcao": -2.5,
    "falhou": -2.5, "fracasso": -3.0, "pior": -2.5, "lixo": -3.0,
    "abandono": -2.0, "abandonou": -2.5, "mentira": -2.5, "mentiroso": -2.5,
    "prejudicou": -2.5, "prejuízo": -2.0, "prejuizo": -2.0, "danoso": -2.0,
    "crime": -3.0, "criminoso": -3.0, "acusação": -2.0, "acusacao": -2.0,
    "escândalo": -3.0, "escandalo": -3.0, "denúncia": -2.0, "denuncia": -2.0,
}
_NEGACOES = {
    "não", "nao", "nunca", "jamais", "nem", "tampouco",
    "sem", "falta", "deixa", "deixam", "recusa",
}


class AnalisadorSentimento:
    """Classifica sentimento (positivo/negativo/neutro) usando VADER + léxico PT."""

    LIMIAR_POSITIVO = 0.05
    LIMIAR_NEGATIVO = -0.05

    def __init__(self) -> None:
        self.analisador = SentimentIntensityAnalyzer()
        self._expandir_lexico_pt()

    def _expandir_lexico_pt(self) -> None:
        self.analisador.lexicon.update(_LEXICO_POSITIVO)
        self.analisador.lexicon.update(_LEXICO_NEGATIVO)
        vader_mod.NEGATE.extend(_NEGACOES)
        logger.info("Léxico PT carregado: %d termos positivos, %d negativos, %d negações",
                    len(_LEXICO_POSITIVO), len(_LEXICO_NEGATIVO), len(_NEGACOES))

    def classificar(self, texto: str) -> str:
        if not texto:
            return SENTIMENTO_NEUTRO
        composto = self.analisador.polarity_scores(texto)["compound"]
        if composto >= self.LIMIAR_POSITIVO:
            return SENTIMENTO_POSITIVO
        if composto <= self.LIMIAR_NEGATIVO:
            return SENTIMENTO_NEGATIVO
        return SENTIMENTO_NEUTRO

    def aplicar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "texto_limpo" not in df.columns:
            return df
        df["sentimento"] = df["texto_limpo"].map(self.classificar)
        logger.info(
            "Sentimento aplicado: %s",
            df["sentimento"].value_counts().to_dict(),
        )
        return df