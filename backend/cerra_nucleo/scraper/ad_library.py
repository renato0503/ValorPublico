"""Meta Ad Library (anuncios politicos) — API oficial e gratuita (plano 06 §6).

Requisito: app na Meta com `ads_read` + identidade confirmada. Sem isso o
endpoint devolve 401/403 e o modulo falha silenciosamente (o app mostra
"anuncios indisponiveis ate a aprovacao da Meta").

Somente dados **agregados** no Firestore (plano 05 §6): quem pagou, faixa de
gasto e estados alcancados. Nada de lista de pessoas.
"""

from __future__ import annotations

import requests

ENDPOINT = "https://graph.facebook.com/v21.0/ads_archive"
PAUSA = 2.0

CAMPOS = (
    "id,page_name,bylines,ad_creative_bodies,ad_delivery_start_time,"
    "ad_delivery_stop_time,spend,impressions,demographic_distribution,"
    "delivery_by_region,publisher_platforms"
)


def _faixa_para_meio(spend: str) -> float:
    """A Meta devolve faixas ('500 - 1000'). Devolve o ponto medio."""
    if not spend:
        return 0.0
    numeros = [n.replace(",", ".") for n in __import__("re").findall(r"[\d.,]+", spend)]
    valores = []
    for n in numeros:
        try:
            valores.append(float(n))
        except ValueError:
            continue
    if not valores:
        return 0.0
    if len(valores) == 1:
        return valores[0]
    return (min(valores) + max(valores)) / 2


def consultar(
    token: str,
    pais: str = "BR",
    termos: list[str] | None = None,
    limite: int = 50,
    timeout: float = 30.0,
) -> tuple[list[dict], str | None]:
    """Busca anuncios politicos ativos no pais.

    Devolve ([{anunciante, pagou, gasto_faixa, gasto_estimado, inicio, fim,
    texto, estados, plataformas}], erro).
    """
    if not token:
        return [], "Sem token da Meta Ad Library (app com ads_read + identidade confirmada)."

    params: dict[str, object] = {
        "access_token": token,
        "ad_reached_countries": json_lista(pais),
        "ad_type": "POLITICAL_AND_ISSUE_ADS",
        "ad_active_status": "ALL",
        "fields": CAMPOS,
        "limit": max(1, min(int(limite), 100)),
    }
    if termos:
        params["search_terms"] = json_lista(" ".join(termos))

    try:
        resp = requests.get(ENDPOINT, params=params, timeout=timeout)
        if resp.status_code in (401, 403):
            return [], (
                f"Ad Library respondeu {resp.status_code}: app da Meta nao aprovado "
                "ou token sem permissao ads_read."
            )
        resp.raise_for_status()
        dados = resp.json()
    except Exception as exc:  # noqa: BLE001
        return [], f"Ad Library indisponivel: {exc}"

    saida: list[dict] = []
    for anuncio in dados.get("data", []):
        delivery = anuncio.get("delivery_by_region") or {}
        estados = {}
        for entrada in delivery.get("region_delivery", []) if isinstance(delivery, dict) else []:
            regiao = entrada.get("region", "")
            pct = float(entrada.get("percent") or 0)
            if regiao:
                estados[regiao] = pct
        corpos = anuncio.get("ad_creative_bodies") or []
        saida.append(
            {
                "id": anuncio.get("id", ""),
                "anunciante": anuncio.get("page_name", ""),
                "pagou": ", ".join(anuncio.get("bylines") or []),
                "gasto_faixa": anuncio.get("spend", ""),
                "gasto_estimado": _faixa_para_meio(anuncio.get("spend", "")),
                "impressoes": anuncio.get("impressions", ""),
                "inicio": anuncio.get("ad_delivery_start_time", ""),
                "fim": anuncio.get("ad_delivery_stop_time", ""),
                "texto": " ".join(str(c) for c in corpos)[:400],
                "estados": estados,
                "plataformas": anuncio.get("publisher_platforms") or [],
            }
        )
    return saida, None


def json_lista(valores) -> str:
    """A API espera JSON array em parametros de query."""
    import json

    if isinstance(valores, (list, tuple)):
        return json.dumps(list(valores))
    return json.dumps([valores])


def agregar_por_estado(anuncios: list[dict], estado: str = "MT") -> dict:
    """Agregado por estado: quanto de gasto alcancou MT (plano 14 K-22)."""
    ativos = 0
    gasto = 0.0
    por_anunciante: dict[str, float] = {}
    for anuncio in anuncios or []:
        pct = float((anuncio.get("estados") or {}).get(estado, 0))
        if pct <= 0:
            continue
        ativos += 1
        valor = float(anuncio.get("gasto_estimado") or 0) * (pct / 100.0)
        gasto += valor
        nome = anuncio.get("pagou") or anuncio.get("anunciante") or "desconhecido"
        por_anunciante[nome] = por_anunciante.get(nome, 0.0) + valor
    return {
        "estado": estado,
        "anuncios_ativos": ativos,
        "gasto_estimado": round(gasto, 2),
        "por_anunciante": dict(sorted(por_anunciante.items(), key=lambda kv: -kv[1])[:50]),
    }
