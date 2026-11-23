"""Metricas de cobertura e SLA do monitoramento (qualidade do servico).

O que o mercado chama de "cobertura" e o que o cliente exige no contrato:
  - quais fontes/entidades foram efetivamente monitoradas;
  - quanto tempo levou entre a publicacao e a disponibilidade do clipping
    (latencia = o argumento de venda "saber antes");
  - quais fontes falharam / nao retornaram no periodo;
  - tier dos veiculos (Tier 1/2/3) para priorizar o escopo.

O pipeline ja grava `data_publicacao` (quando a fonte expoe) e `created_at`
(momento em que gravamos no Firestore). A diferenca entre os dois e o SLA
observado - e o mesmo dado que sustenta o "tempo recorde" do DSM.
"""

from datetime import datetime, timezone

# Veiculos considerados de alto impacto (Tier 1) por categoria.
# A lista pode ser sobreposta por settings (TIER1_VEICULOS).
TIER1_PADRAO = {
    "g1", "globo", "folha", "estadao", "uol", "terra", "estadao de mato grosso",
    "gazeta mt", "mtvnews", "cnn brasil", "band", "sbt", "record", "rede globo",
    "globonews", "jornal da cidade", "diario de cuiaba", "prima/news cuiaba",
    "agencia brazil", "agencia rbs", "radio cuiaba", "tv cuiaba", "gazeta",
}

# Lags acima disso sao considerados inconsistentes (migracao/epoch) e ficam
# fora do calculo de SLA.
LAG_MAX_MINUTOS = 7 * 24 * 60

TIER2_PADRAO = {
    "folha de cuiaba", "agora mt", "prima news", "midiastories", "loca news",
    "radio bandeirantes", "radio itatiaia", "radio sota", "tv local",
}


def _parse_dt(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    if isinstance(valor, str) and valor:
        try:
            dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def tier_do_veiculo(veiculo: str, tier1: set[str] | None = None, tier2: set[str] | None = None) -> str:
    """Classifica o veiculo em Tier 1 / Tier 2 / Tier 3."""
    if not veiculo:
        return "Tier 3"
    chave = veiculo.strip().lower()
    tier1 = tier1 if tier1 is not None else TIER1_PADRAO
    tier2 = tier2 if tier2 is not None else TIER2_PADRAO
    if chave in tier1:
        return "Tier 1"
    if chave in tier2:
        return "Tier 2"
    return "Tier 3"


def _percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    pos = (len(ordenados) - 1) * p
    baixo = int(pos)
    alto = min(baixo + 1, len(ordenados) - 1)
    frac = pos - baixo
    return ordenados[baixo] * (1 - frac) + ordenados[alto] * frac


def analisar_cobertura(
    clippings: list[dict],
    tier1: set[str] | None = None,
    tier2: set[str] | None = None,
    veiculos_esperados: list[str] | None = None,
) -> dict:
    """Calcula SLA, cobertura por fonte/tier e falhas observadas.

    Retorna dict com:
        total, com_data, com_veiculo, pct_cobertura
        sla_min_medio, sla_min_p95, sla_min_mediano
        por_veiculo: {veiculo: {itens, tier, sla_medio}}
        por_tier: {tier: n}
        veiculos_esperados, veiculos_ausentes
        sem_data_publicacao (quantidade - sinal de falha de extracao)
    """
    total = len(clippings)
    if total == 0:
        return {
            "total": 0, "com_data": 0, "com_veiculo": 0, "pct_cobertura": 0.0,
            "sla_min_medio": 0.0, "sla_min_p95": 0.0, "sla_min_mediano": 0.0,
            "por_veiculo": {}, "por_tier": {}, "veiculos_esperados": [],
            "veiculos_ausentes": [], "sem_data_publicacao": 0,
        }

    lags: list[float] = []
    por_veiculo: dict[str, dict] = {}
    por_tier: dict[str, int] = {}
    com_data = 0
    com_veiculo = 0
    sem_data = 0

    for clipping in clippings:
        metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
        veiculo = (metadados.get("veiculo") or clipping.get("autor") or "").strip()
        if veiculo:
            com_veiculo += 1
        publicacao = _parse_dt(clipping.get("data_publicacao"))
        criado = _parse_dt(clipping.get("created_at"))
        if publicacao and criado:
            com_data += 1
            delta = (criado - publicacao).total_seconds() / 60.0
            # Lags implausiveis (migracao de dados, epoch, datas divergentes)
            # nao entram no SLA: so o que foi coletado em tempo real conta.
            if 0 <= delta <= LAG_MAX_MINUTOS:
                lags.append(delta)
        elif not publicacao:
            sem_data += 1

        if veiculo:
            tier = tier_do_veiculo(veiculo, tier1, tier2)
            por_tier[tier] = por_tier.get(tier, 0) + 1
            registro = por_veiculo.setdefault(
                veiculo, {"itens": 0, "tier": tier, "sla_medio": 0.0, "_lags": []}
            )
            registro["itens"] += 1
            if publicacao and criado:
                delta = (criado - publicacao).total_seconds() / 60.0
                if 0 <= delta <= LAG_MAX_MINUTOS:
                    registro["_lags"].append(delta)

    for veiculo, registro in por_veiculo.items():
        lags_veiculo = registro.pop("_lags", [])
        registro["sla_medio"] = round(sum(lags_veiculo) / len(lags_veiculo), 1) if lags_veiculo else 0.0

    esperados = [str(v).strip().lower() for v in (veiculos_esperados or []) if str(v).strip()]
    observados = {v.lower() for v in por_veiculo}
    ausentes = sorted(v for v in esperados if v not in observados)

    return {
        "total": total,
        "com_data": com_data,
        "com_veiculo": com_veiculo,
        "pct_cobertura": round(100.0 * com_veiculo / total, 1),
        "sla_min_medio": round(sum(lags) / len(lags), 1) if lags else 0.0,
        "sla_min_p95": round(_percentil(lags, 0.95), 1),
        "sla_min_mediano": round(_percentil(lags, 0.5), 1),
        "por_veiculo": dict(sorted(por_veiculo.items(), key=lambda kv: -kv[1]["itens"])[:40]),
        "por_tier": por_tier,
        "veiculos_esperados": esperados,
        "veiculos_ausentes": ausentes,
        "sem_data_publicacao": sem_data,
        "itens_com_sla": len(lags),
    }

