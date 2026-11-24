"""Indice de crise (K-28) e previsao (K-33) do catalogo 14.

K-28: z-score dos negativos nas ultimas 24 h contra a media e o desvio dos
ultimos 28 dias. Crise quando z >= 3 e n >= 5 (regra do plano 07 §2).

K-33: projecao de 4 semanas das mencoes (K-01) e do saldo de opiniao (K-03),
com faixa de 80%. Usa `statsforecast` (Apache-2.0, leve, CPU) e, se
`prophet` estiver instalado, usa o Prophet. Nao ha API paga.

Regra do dono: projecao e **estatistica**, nao promessa. O app sempre mostra a
faixa de margem.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

# --------------------------------------------------------------------------
# K-28 — indice de crise
# --------------------------------------------------------------------------
Z_CRISE = 3.0
MINIMO_ITENS = 5
JANELA_BASE_DIAS = 28
JANELA_CRISE_HORAS = 24


def indice_crise(
    serie_negativos: dict[str, int],
    agora: datetime | None = None,
    z_limite: float = Z_CRISE,
    minimo_itens: int = MINIMO_ITENS,
    janela_base_dias: int = JANELA_BASE_DIAS,
    janela_crise_horas: int = JANELA_CRISE_HORAS,
) -> dict:
    """Calcula o indice de crise a partir da serie diaria de negativos.

    `serie_negativos`: {"2026-11-20": 3, "2026-11-21": 1, ...}
    Devolve:
        {
          "ativo": bool, "z": float, "negativos_24h": int,
          "media_base": float, "desvio_base": float,
          "fator": float, "periodo": "...", "mensagem": "..."
        }
    """
    agora = agora or datetime.now(timezone.utc)
    hoje = agora.date()
    inicio_janela = hoje - timedelta(days=janela_base_dias)

    # Serie numerica (datas ordenadas)
    pontos: list[tuple[date, int]] = []
    for chave, valor in (serie_negativos or {}).items():
        try:
            d = datetime.strptime(str(chave)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        pontos.append((d, int(valor or 0)))
    pontos.sort()

    # Base: ultimos N dias (exclui a janela de crise de 24 h)
    base = [v for d, v in pontos if inicio_janela <= d < hoje]
    # Serie recente: ultimas 24 h (hoje + parte de ontem)
    corte = agora - timedelta(hours=janela_crise_horas)
    recentes = 0
    for d, v in pontos:
        if d == hoje:
            recentes += v
        elif d == hoje - timedelta(days=1):
            # Considera so se a data caem dentro da janela de 24 h
            if d >= corte.date():
                recentes += v

    if not base:
        return {
            "ativo": False,
            "z": 0.0,
            "negativos_24h": recentes,
            "media_base": 0.0,
            "desvio_base": 0.0,
            "fator": 0.0,
            "periodo": f"{hoje.isoformat()}",
            "mensagem": "Sem historico suficiente para medir a crise (base de 28 dias vazia).",
        }

    media = sum(base) / len(base)
    variancia = sum((v - media) ** 2 for v in base) / len(base)
    desvio = math.sqrt(variancia)
    # Serie constante: o desvio e zero e o z-score explode. Usa um piso de 0,5
    # para manter o numero interpretavel (e o alerta, acionavel).
    desvio_efetivo = desvio if desvio > 0 else 0.5

    z = (recentes - media) / desvio_efetivo

    ativo = bool(recentes >= minimo_itens and z >= z_limite)
    fator = (recentes / media) if media > 0 else (float("inf") if recentes > 0 else 0.0)

    if ativo:
        mensagem = (
            f"Negativos {recentes} nas ultimas 24 h, {fator:.1f}x a media "
            f"de {media:.1f} por dia (limite: {z_limite:.0f} desvios). "
            "Vale olhar a linha do tempo antes de responder."
        )
    elif recentes >= minimo_itens and z >= z_limite * 0.6:
        mensagem = (
            f"Negativos {recentes} nas ultimas 24 h, acima da media de "
            f"{media:.1f} mas ainda dentro do normal. Fique de olho."
        )
    else:
        mensagem = (
            f"Negativos {recentes} nas ultimas 24 h, dentro do normal "
            f"(media de {media:.1f} por dia)."
        )

    return {
        "ativo": ativo,
        "z": round(z, 2),
        "negativos_24h": recentes,
        "media_base": round(media, 3),
        "desvio_base": round(desvio, 3),
        "fator": round(fator, 2) if math.isfinite(fator) else 999.0,
        "periodo": hoje.isoformat(),
        "mensagem": mensagem,
    }


# --------------------------------------------------------------------------
# K-33 — projecao de 4 semanas
# --------------------------------------------------------------------------
def _serie_para_dataframe(serie: dict[str, float]):
    import pandas as pd

    linhas = []
    for chave, valor in (serie or {}).items():
        try:
            d = datetime.strptime(str(chave)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        linhas.append((pd.Timestamp(d), float(valor or 0)))
    if not linhas:
        return None
    df = pd.DataFrame(linhas, columns=["ds", "y"]).sort_values("ds").reset_index(drop=True)
    # `statsforecast` exige a coluna `unique_id` (uma serie por id).
    df["unique_id"] = "serie"
    return df


def projetar(
    serie: dict[str, float],
    horizonte_dias: int = 28,
    nivel: float = 0.80,
    usar_prophet: bool = True,
) -> dict:
    """Projeta a serie diaria para as proximas semanas.

    Devolve {"metodo", "previsao": [{"data", "valor", "inferior", "superior"}],
             "historico": [...], "erro": str|None}
    """
    df = _serie_para_dataframe(serie)
    if df is None or len(df) < 7:
        return {
            "metodo": "indisponivel",
            "previsao": [],
            "historico": [],
            "erro": "Serie curta demais (menos de 7 dias) para projetar.",
        }

    historico = [
        {"data": row.ds.date().isoformat(), "valor": float(row.y)} for row in df.itertuples()
    ]

    metodo = "statsforecast"
    previsao: list[dict] = []
    try:
        if usar_prophet:
            import prophet  # noqa: F401

            from prophet import Prophet

            dados = df[["ds", "y"]].copy()
            m = Prophet(interval_width=nivel, weekly_seasonality=True, daily_seasonality=False)
            m.fit(dados)
            futuro = m.make_future_dataframe(periods=horizonte_dias, freq="D")
            pred = m.predict(futuro)
            for i in range(len(dados), len(pred)):
                previsao.append(
                    {
                        "data": pred["ds"][i].date().isoformat(),
                        "valor": float(pred["yhat"][i]),
                        "inferior": float(pred["yhat_lower"][i]),
                        "superior": float(pred["yhat_upper"][i]),
                    }
                )
            metodo = "prophet"
        else:
            raise ImportError("prophet nao instalado")
    except ImportError:
        try:
            from statsforecast import StatsForecast
            from statsforecast.models import AutoETS

            sf = StatsForecast(models=[AutoETS(season_length=7)], freq="D", n_jobs=1)
            sf.fit(df[["ds", "y", "unique_id"]].copy())
            pred = sf.predict(h=horizonte_dias)
            ds = pred["ds"]
            media = pred["AutoETS"]
            inferior = pred.get("AutoETS_lo", media)
            superior = pred.get("AutoETS_hi", media)
            for i in range(len(ds)):
                previsao.append(
                    {
                        "data": ds[i].date().isoformat(),
                        "valor": float(media[i]),
                        "inferior": float(inferior[i]),
                        "superior": float(superior[i]),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            return {
                "metodo": "indisponivel",
                "previsao": [],
                "historico": historico,
                "erro": f"Falha ao projetar: {exc}",
            }

    return {"metodo": metodo, "previsao": previsao, "historico": historico, "erro": None}


def resumo_projeccao(resultado: dict) -> str:
    """Frase curta para o tooltip do KPI K-33 (sem prometer nada)."""
    if not resultado or not resultado.get("previsao"):
        return "Sem dados suficientes para projetar as proximas semanas."
    proj = resultado["previsao"]
    primeiro = proj[0]
    ultimo = proj[-1]
    return (
        f"Projecao de {len(proj)} dias: de {primeiro['valor']:.0f} para "
        f"{ultimo['valor']:.0f} (faixa de {ultimo['inferior']:.0f} a "
        f"{ultimo['superior']:.0f}). Projecao estatistica, nao promessa."
    )


def agrupar_por_dia(itens: list[dict], campo_data: str = "data_publicacao") -> dict[str, int]:
    """Agrupa uma lista de itens por dia -> contagem (serie para o calculo)."""
    contagem: dict[str, int] = defaultdict(int)
    for item in itens or []:
        bruto = item.get(campo_data)
        if isinstance(bruto, datetime):
            chave = bruto.date().isoformat()
        elif isinstance(bruto, date):
            chave = bruto.isoformat()
        else:
            texto = str(bruto or "")[:10]
            try:
                datetime.strptime(texto, "%Y-%m-%d")
                chave = texto
            except ValueError:
                continue
        contagem[chave] += 1
    return dict(contagem)


def _utc_hoje() -> datetime:
    return datetime.now(timezone.utc)
