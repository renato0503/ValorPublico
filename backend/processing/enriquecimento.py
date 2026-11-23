"""Enriquecimento de clipping: a camada que transforma coleta em inteligencia.

Aplica, sobre um clipping, os modulos da "Camada DSM":

  - mencao         (direta / indireta / indeterminada + papel + porta-vozes)
  - trecho         (recorte citado + destaque de palavras-chave)
  - compliance     (Lei 9.504/1997 - alertas eleitorais)
  - propaganda     (radar: materia jornalistica x propaganda publica)
  - valoracao AVPE (centimetragem / R$ por cm2 / R$ por minuto)

Cada campo gravado e autocontido e auditavel (guarda os "motivos" da
classificacao), para que o painel consiga explicar por que um clipping foi
marcado como negativo, direto ou fora de compliance.
"""

import pandas as pd

from processing import compliance_eleitoral
from processing import propaganda_publica
from processing.mencao import classificar_mencao
from processing.trecho import extrair_trecho

CAMPOS_ENRIQUECIDOS = (
    "mencao",
    "trecho",
    "compliance",
    "propaganda_publica",
    "valor_avpe",
    "espaco_cm2",
)


def _termos_do_clipping(clipping: dict, agente: dict | None) -> list[str]:
    metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
    termos = metadados.get("termos_de_busca")
    if isinstance(termos, (list, tuple)):
        return [str(t) for t in termos]
    if agente:
        return [
            str(t)
            for t in (agente.get("termos_de_busca") or [])
            if str(t).strip()
        ]
    return []


def enriquecer_clipping(
    clipping: dict,
    agente: dict | None = None,
    compliance_habilitado: bool = True,
) -> dict:
    """Devolve o clipping acrescido dos campos de inteligencia."""
    texto = clipping.get("texto_limpo", "") or ""
    termos = _termos_do_clipping(clipping, agente)

    mencao = classificar_mencao(texto, termos, agente)
    trecho = extrair_trecho(texto, termos)

    compliance: list[dict] = []
    if compliance_habilitado:
        compliance = compliance_eleitoral.analisar(clipping)

    radar = propaganda_publica.detectar(clipping)

    enriquecido = dict(clipping)
    enriquecido["mencao"] = mencao
    enriquecido["tipo_mencao"] = mencao.get("tipo", "")
    enriquecido["papel_mencao"] = mencao.get("papel", "")
    enriquecido["trecho"] = trecho
    enriquecido["compliance"] = compliance
    enriquecido["compliance_nivel"] = compliance_eleitoral.nivel_maximo(compliance)
    enriquecido["propaganda_publica"] = radar
    return enriquecido


def campos_para_salvar(clipping_enriquecido: dict) -> dict:
    """Seleciona apenas os campos de inteligencia para gravar no Firestore."""
    return {
        "mencao": clipping_enriquecido.get("mencao"),
        "tipo_mencao": clipping_enriquecido.get("tipo_mencao"),
        "papel_mencao": clipping_enriquecido.get("papel_mencao"),
        "trecho": clipping_enriquecido.get("trecho"),
        "compliance": clipping_enriquecido.get("compliance") or [],
        "compliance_nivel": clipping_enriquecido.get("compliance_nivel", ""),
        "propaganda_publica": clipping_enriquecido.get("propaganda_publica"),
    }


def enriquecer_dataframe(df, agente: dict | None = None, compliance_habilitado: bool = True):
    """Aplica o enriquecimento linha a linha do DataFrame de clippings."""
    if df is None or df.empty:
        return df
    from processing.compliance_eleitoral import CALENDARIO_ELEITORAL  # noqa: F401

    registros = []
    for _, row in df.iterrows():
        dados = row.to_dict()
        enriquecido = enriquecer_clipping(
            dados,
            agente=agente,
            compliance_habilitado=compliance_habilitado,
        )
        registros.append(enriquecido)
    return pd.DataFrame(registros)

