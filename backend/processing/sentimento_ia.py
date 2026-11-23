"""Classificação de sentimento via LLM (OpenAI-compatível), com fallback VADER.

Alternativa ao VADER para contextos em que a análise heurística perde nuances
(sarcasmo, ironia, contexto político). Quando desabilitado ou sem API key, cai
no `AnalisadorSentimento` (VADER + léxico PT) — comportamento padrão.

Configuração (.env):
    IA_SENTIMENTO_ENABLED=1
    IA_SENTIMENTO_BASE_URL=https://api.openai.com/v1   # OpenAI-compatível
    IA_SENTIMENTO_API_KEY=sk-...
    IA_SENTIMENTO_MODEL=gpt-4o-mini
    IA_SENTIMENTO_MAX_ITENS=200   # limite de itens por execução (custo)
    IA_SENTIMENTO_TAMANHO_LOTE=20 # textos por chamada
"""

import json

import httpx
import pandas as pd

from config import settings
from core.logger import get_logger
from processing.sentiment import AnalisadorSentimento
from scraper.models import (
    SENTIMENTO_NEGATIVO,
    SENTIMENTO_NEUTRO,
    SENTIMENTO_POSITIVO,
)

logger = get_logger(__name__)

_SISTEMA = (
    "Você é um analista de sentimento de mídia política brasileira. "
    "Classifique o sentimento de cada texto em relação ao agente público citado. "
    "Responda APENAS com um JSON array, um objeto por texto, no formato "
    '[{"indice": 0, "sentimento": "positivo|neutro|negativo"}]. '
    "Use 'neutro' para relato factual/sem avaliação; 'positivo'/'negativo' para "
    "elogios, críticas, apoio ou rejeição explícitos ao agente."
)


def _extrair_json(texto_resposta: str) -> list | None:
    """Extrai o JSON array da resposta do modelo de forma tolerante."""
    try:
        return json.loads(texto_resposta)
    except json.JSONDecodeError:
        inicio = texto_resposta.find("[")
        fim = texto_resposta.rfind("]")
        if inicio != -1 and fim != -1 and fim > inicio:
            try:
                return json.loads(texto_resposta[inicio : fim + 1])
            except json.JSONDecodeError:
                return None
    return None


class AnalisadorSentimentoIA:
    """Classifica sentimento via LLM com fallback automático para VADER."""

    _ROTULOS_VALIDOS = {
        SENTIMENTO_POSITIVO,
        SENTIMENTO_NEUTRO,
        SENTIMENTO_NEGATIVO,
    }

    def __init__(self) -> None:
        self.base_url = (settings.IA_SENTIMENTO_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        self.api_key = settings.IA_SENTIMENTO_API_KEY
        self.model = settings.IA_SENTIMENTO_MODEL or "gpt-4o-mini"
        self.max_itens = max(0, settings.IA_SENTIMENTO_MAX_ITENS)
        self.tamanho_lote = max(1, settings.IA_SENTIMENTO_TAMANHO_LOTE)
        self.timeout = settings.IA_SENTIMENTO_TIMEOUT
        self.temperatura = settings.IA_SENTIMENTO_TEMPERATURA
        self.habilitado = settings.IA_SENTIMENTO_ENABLED and bool(self.api_key)
        self.vader = AnalisadorSentimento()
        self._estatisticas = {"ia": 0, "fallback_vader": 0}
        if self.habilitado:
            logger.info(
                "Sentimento via IA habilitado (%s @ %s, máx %d itens/lote %d).",
                self.model, self.base_url, self.max_itens, self.tamanho_lote,
            )
        else:
            logger.info("Sentimento via IA desabilitado (sem API key) — usando VADER.")

    # ------------------------------------------------------------------ API

    def _chamar_lote(self, textos: list[str]) -> list[str] | None:
        """Chama o endpoint /chat/completions para um lote e devolve rotulos."""
        numerados = "\n".join(f"[{i}] {t[:600]}" for i, t in enumerate(textos))
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _SISTEMA},
                        {"role": "user", "content": numerados},
                    ],
                    "temperature": self.temperatura,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            dados = resp.json()
            conteudo = dados["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            logger.warning("Sentimento IA: falha no lote: %s", e)
            return None
        return self._normalizar_resposta(conteudo, len(textos))

    def _normalizar_resposta(self, conteudo: str, n: int) -> list[str] | None:
        itens = _extrair_json(conteudo)
        if not isinstance(itens, list) or not itens:
            return None
        por_indice: dict[int, str] = {}
        for obj in itens:
            if not isinstance(obj, dict):
                continue
            idx = obj.get("indice")
            sent = obj.get("sentimento")
            if isinstance(idx, int) and isinstance(sent, str):
                por_indice[idx] = sent.lower()
        if len(por_indice) < n * 0.5:
            return None
        rotulos = [SENTIMENTO_NEUTRO] * n
        for i in range(n):
            valor = por_indice.get(i)
            if valor in self._ROTULOS_VALIDOS:
                rotulos[i] = valor
        return rotulos

    # ------------------------------------------------------------- interface

    def classificar(self, texto: str) -> str:
        """Classifica UM texto (usa lote de 1 quando chamado isoladamente)."""
        if self.habilitado:
            resultado = self._chamar_lote([texto] if texto else [])
            if resultado and resultado[0] != SENTIMENTO_NEUTRO:
                self._estatisticas["ia"] += 1
                return resultado[0]
        self._estatisticas["fallback_vader"] += 1
        return self.vader.classificar(texto)

    def classificar_lote(self, textos: list[str]) -> list[str]:
        """Classifica uma lista de textos; itens com erro caem para VADER."""
        if not textos:
            return []
        if not self.habilitado:
            return [self.vader.classificar(t) for t in textos]

        rotulos: list[str] = []
        for i in range(0, len(textos), self.tamanho_lote):
            lote = textos[i : i + self.tamanho_lote]
            resultado = self._chamar_lote(lote)
            if resultado is None:
                rotulos.extend(self.vader.classificar(t) for t in lote)
                continue
            for t, r in zip(lote, resultado):
                if r in self._ROTULOS_VALIDOS:
                    self._estatisticas["ia"] += 1
                    rotulos.append(r)
                else:
                    self._estatisticas["fallback_vader"] += 1
                    rotulos.append(self.vader.classificar(t))
        return rotulos

    def aplicar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "texto_limpo" not in df.columns:
            return df
        textos = (df["texto_limpo"].fillna("") if df["texto_limpo"].isna().any()
                  else df["texto_limpo"]).tolist()

        if not self.habilitado or not textos:
            return self.vader.aplicar_dataframe(df)

        limitados = textos[: self.max_itens] if self.max_itens > 0 else textos
        n_fallback = len(textos) - len(limitados)
        rotulos = self.classificar_lote(limitados)
        rotulos.extend([SENTIMENTO_NEUTRO] * n_fallback)
        df["sentimento"] = rotulos[: len(df)]
        logger.info(
            "Sentimento aplicado (%s): ia=%d fallback=%d | %s",
            self.model,
            self._estatisticas["ia"],
            self._estatisticas["fallback_vader"],
            df["sentimento"].value_counts().to_dict(),
        )
        return df