import re

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

# Léxico de domínio: política/administração pública. Vale mais que o VADER
# genérico para decidir o tom de uma notícia sobre o governo.
_DOMINIO_POSITIVO = {
    "entrega": 2.0, "entregou": 2.0, "inaugura": 2.5, "inaugurada": 2.5,
    "investimento": 2.0, "investe": 1.5, "investiu": 1.5, "obra": 1.2,
    "obras": 1.2, "melhoria": 2.0, "melhorias": 2.0, "amplia": 1.8,
    "ampliação": 1.8, "ampliacao": 1.8, "avanço": 2.0, "avanco": 2.0,
    "avança": 1.8, "avanca": 1.8, "conquista": 2.0, "aprovação": 2.0,
    "aprovacao": 2.0, "aprova": 1.5, "sanciona": 2.0, "parceria": 1.2,
    "convênio": 1.2, "convenio": 1.2, "reconhecimento": 2.0, "prêmio": 2.0,
    "premio": 2.0, "selo": 1.2, "homenagem": 1.8, "benefício": 1.8,
    "beneficio": 1.8, "redução": 1.2, "reducao": 1.2, "economia": 1.2,
    "crescimento": 1.5, "desenvolvimento": 1.2, "modernização": 1.5,
    "modernizacao": 1.5, "pagamento": 1.2, "nomeia": 1.0, "recupera": 1.5,
    "regulariza": 1.5, "beneficia": 1.8, "atende": 1.0, "apoia": 1.2,
    "fortalece": 1.2, "sucesso": 2.5, "qualidade": 1.5, "transparência": 1.5,
    "transparencia": 1.5, "combate": 1.2, "vitória": 2.0, "vitoria": 2.0,
    "orgulho": 2.0, "parabéns": 2.5, "parabens": 2.5, "excelente": 3.0,
    "ótimo": 2.5, "otimo": 2.5, "brilhante": 2.5, "competente": 2.0,
    "eficiência": 1.5, "eficiencia": 1.5, "resultado": 1.2, "resultados": 1.2,
    "melhorou": 2.0, "avançou": 2.0, "avancou": 2.0, "vencedor": 1.8,
    "vencedores": 1.8, "vitórias": 2.0, "vitórias": 2.0, "conquistas": 2.0,
    "crescimento": 1.5, "emprego": 1.2, "empregos": 1.2, "renda": 1.0,
    "segurança": 1.0, "reduz": 1.2, "reduziu": 1.2, "recorde": 1.5,
}
_DOMINIO_NEGATIVO = {
    "investiga": 2.5, "investigação": 2.5, "investigacao": 2.5,
    "investigado": 2.5, "irregularidade": 2.8, "irregularidades": 2.8,
    "suspeita": 2.2, "suspeitas": 2.2, "denúncia": 2.5, "denuncia": 2.5,
    "denunciado": 2.5, "corrupção": 3.0, "corrupcao": 3.0, "escândalo": 3.0,
    "escandalo": 3.0, "fraude": 3.0, "desvio": 2.5, "prisão": 2.5,
    "prisao": 2.5, "preso": 2.5, "presa": 2.5, "condenado": 2.8,
    "condenada": 2.8, "réu": 2.0, "reu": 2.0, "operação": 1.5,
    "operacao": 1.5, "crise": 2.5, "greve": 2.0, "protesto": 1.5,
    "crítica": 1.8, "critica": 1.8, "cobrança": 1.5, "cobranca": 1.5,
    "atraso": 1.8, "aumento": 1.5, "corte": 1.8, "corta": 1.8,
    "cortes": 1.8, "queda": 1.5, "morte": 2.5, "acidente": 2.0,
    "crime": 2.5, "crimes": 2.5, "acusação": 2.0, "acusacao": 2.0,
    "processo": 1.2, "improbidade": 3.0, "inelegível": 2.5, "inelegivel": 2.5,
    "condenação": 2.8, "condenacao": 2.8, "rejeição": 2.0, "rejeicao": 2.0,
    "dívida": 1.8, "divida": 1.8, "rombo": 2.5, "falha": 2.0, "falhas": 2.0,
    "problema": 1.8, "problemas": 1.8, "perda": 1.8, "alerta": 1.5,
    "caos": 2.5, "tumulto": 2.0, "vandalismo": 2.5, "incêndio": 2.0,
    "incendio": 2.0, "seca": 1.5, "enchente": 1.5, "sonegação": 2.5,
    "sonegacao": 2.5, "desmatamento": 2.0, "garimpo": 1.5, "ilegal": 2.2,
    "violência": 2.5, "violencia": 2.5, "homicídio": 3.0, "homicidio": 3.0,
    "roubo": 2.2, "roubos": 2.2, "furto": 2.0, "furtos": 2.0,
    "assalto": 2.2, "nepotismo": 2.5, "rachadinha": 2.5, "vergonha": 2.5,
    "péssimo": 3.0, "pessimo": 3.0, "pior": 2.5, "fracasso": 3.0,
    "abandono": 2.0, "mentira": 2.5, "negligência": 2.5, "negligencia": 2.5,
    "omissão": 2.0, "omissao": 2.0, "superfaturamento": 3.0,
    "precariedade": 2.0, "precarização": 2.0, "precarizacao": 2.0,
    "esquema": 2.0, "propina": 3.0, "lavagem": 2.5, "bloqueio": 1.8,
    "demissão": 2.0, "demissao": 2.0, "demissões": 2.0, "demissoes": 2.0,
}
_FRASES_POSITIVAS = (
    "reduzir gastos", "assume obras", "ordena recursos", "roubos caem",
    "queda do crime", "entrega de obras", "geração de emprego",
    "geração de empregos", "redução de gastos", "reducao de gastos",
    "selo diamante", "boas notícias", "boas noticias",
    "anunciam vencedores", "custeio de leitos", "ordena recursos",
    "roubos de veículos caem", "roubos de veiculos caem",
    "criminalidade cai", "crime cai",
)
_FRASES_NEGATIVAS = (
    "falta de prestação", "falta de prestacao", "profeta do caos",
    "alerta fiscal", "licitação irregular", "licitacao irregular",
    "desvio de verba", "dinheiro público", "dinheiro publico",
)


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

    @staticmethod
    def _contar_dominio(texto: str) -> tuple[float, float]:
        normalizado = texto.lower()
        palavras = re.findall(r"[a-záàâãéêíóôõúç0-9]+", normalizado)
        positivo = sum(_DOMINIO_POSITIVO.get(p, 0.0) for p in palavras)
        negativo = sum(_DOMINIO_NEGATIVO.get(p, 0.0) for p in palavras)
        positivo += sum(1.8 for frase in _FRASES_POSITIVAS if frase in normalizado)
        negativo += sum(1.8 for frase in _FRASES_NEGATIVAS if frase in normalizado)
        for frase in ("roubos de veículos caem", "roubos de veiculos caem", "criminalidade cai", "crime cai"):
            if frase in normalizado:
                positivo += 2.2
        # O título carrega mais peso que o corpo.
        titulo = normalizado.splitlines()[0][:300]
        positivo += sum(1.0 for frase in _FRASES_POSITIVAS if frase in titulo)
        negativo += sum(1.0 for frase in _FRASES_NEGATIVAS if frase in titulo)
        return positivo, negativo

    def classificar(self, texto: str) -> str:
        if not texto:
            return SENTIMENTO_NEUTRO
        positivo, negativo = self._contar_dominio(texto[:1800])
        if positivo >= 2.0 and positivo > negativo * 1.35:
            return SENTIMENTO_POSITIVO
        if negativo >= 2.0 and negativo > positivo * 1.35:
            return SENTIMENTO_NEGATIVO
        composto = self.analisador.polarity_scores(texto)["compound"]
        if composto >= 0.6 and positivo >= negativo:
            return SENTIMENTO_POSITIVO
        if composto <= -0.6 and negativo >= positivo:
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
