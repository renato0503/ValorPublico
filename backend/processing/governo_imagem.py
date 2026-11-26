"""Indicadores da tela "Imagem" do Governo de MT (plano 22).

Tudo calculado sobre a base de notícias saneada (e, no caso dos canais, também
sobre os comentários do público no Instagram oficial):

* ``imagem_institucional`` (0 a 100): 50 é neutro. Sobe com notícias positivas
  e desce com negativas sobre o Executivo; veículos de grande audiência (Tier 1)
  pesam o dobro.
* ``pct_tier1``: parte das notícias publicadas por grandes portais e jornais.
* ``por_canal``: tom (positivo/neutro/negativo) por tipo de canal.
* ``especificidades.semana_vs_base``: palavras que apareceram muito mais (ou
  muito menos) nos últimos 7 dias do que nas semanas anteriores.
* ``crise_eventos``: dias em que as notícias negativas saíram da faixa normal,
  com as manchetes que puxaram o pico.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from processing.lexico import legiveis, relevante, sem_veiculo
from processing.nuvem import extrair_palavras
from processing.veiculos_mt import classificar

TONS = ("positivo", "neutro", "negativo")


def _data(item: dict) -> datetime | None:
    bruto = item.get("data_publicacao") or item.get("data")
    if isinstance(bruto, datetime):
        return bruto if bruto.tzinfo else bruto.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _tom(item: dict) -> str:
    tom = item.get("sentimento") or "neutro"
    return tom if tom in TONS else "neutro"


def imagem_e_canais(itens: list[dict], comentarios_instagram: list[dict] | None = None) -> dict:
    peso_total = 0.0
    saldo = 0.0
    tier1 = 0
    por_canal: dict[str, Counter] = defaultdict(Counter)
    por_tier: Counter = Counter()
    for item in itens:
        info = classificar(item.get("veiculo", ""))
        tom = _tom(item)
        por_canal[info["canal"]][tom] += 1
        if info["tier"]:
            por_tier[info["tier"]] += 1
        if info["tier"] == "Tier 1":
            tier1 += 1
        if item.get("escopo") == "governo-estado":
            peso = 2.0 if info["tier"] == "Tier 1" else 1.0
            peso_total += peso
            saldo += peso * (1 if tom == "positivo" else -1 if tom == "negativo" else 0)
    for comentario in comentarios_instagram or []:
        conta = comentario.get("conta") or "Instagram"
        por_canal[f"Comentários no Instagram ({conta})"][_tom(comentario)] += 1
    imagem = round(50 + 50 * saldo / peso_total) if peso_total else None
    return {
        "imagem_institucional": imagem,
        "imagem_metodo": "50 = neutro; notícias positivas sobre o Executivo somam, negativas subtraem; Tier 1 pesa 2.",
        "pct_tier1": round(100 * tier1 / len(itens), 1) if itens else None,
        "por_tier": dict(por_tier),
        "por_canal": {
            canal: {t: int(c.get(t, 0)) for t in TONS}
            for canal, c in sorted(por_canal.items(), key=lambda kv: -sum(kv[1].values()))
        },
    }


def semana_vs_base(itens: list[dict], dias_semana: int = 7, dias_base: int = 56, n: int = 10) -> dict:
    fim = max((d for d in (_data(i) for i in itens) if d), default=datetime.now(timezone.utc))
    ini_semana = fim - timedelta(days=dias_semana)
    ini_base = ini_semana - timedelta(days=dias_base)
    f_sem: Counter = Counter()
    f_base: Counter = Counter()
    titulos_sem: list[str] = []
    n_sem = n_base = 0
    for item in itens:
        d = _data(item)
        if not d or d < ini_base:
            continue
        palavras = {p for p in extrair_palavras(item.get("titulo", "")) if relevante(p)}
        if d >= ini_semana:
            f_sem.update(palavras)
            n_sem += 1
            titulos_sem.append(sem_veiculo(item.get("titulo", "")))
        else:
            f_base.update(palavras)
            n_base += 1
    if not n_sem or not n_base:
        return {"mais": [], "menos": [], "n_semana": n_sem, "n_base": n_base}
    pontos = []
    for palavra in set(f_sem) | set(f_base):
        esperado = n_sem * (f_base[palavra] + 0.5) / n_base
        z = (f_sem[palavra] - esperado) / math.sqrt(esperado + 1)
        pontos.append((palavra, z, f_sem[palavra], f_base[palavra]))
    mais = [p for p in sorted(pontos, key=lambda x: -x[1]) if p[2] >= 3][:n]
    menos = [p for p in sorted(pontos, key=lambda x: x[1]) if p[3] >= 8 and p[1] < 0][:n]
    nomes = legiveis([p[0] for p in mais + menos], titulos_sem)
    fmt = lambda lista: [  # noqa: E731
        {"palavra": nomes.get(p, p), "valor": round(abs(z), 1), "semana": a, "antes": b}
        for p, z, a, b in lista
    ]
    return {
        "mais": fmt(mais),
        "menos": fmt(menos),
        "n_semana": n_sem,
        "n_base": n_base,
        "periodo": {"semana_de": ini_semana.date().isoformat(), "ate": fim.date().isoformat()},
    }


def eventos_crise(itens: list[dict], dias: int = 60, maximo: int = 8) -> list[dict]:
    fim = max((d for d in (_data(i) for i in itens) if d), default=datetime.now(timezone.utc))
    inicio = (fim - timedelta(days=dias)).date()
    por_dia: dict[str, list[dict]] = defaultdict(list)
    for item in itens:
        d = _data(item)
        if d and d.date() >= inicio:
            por_dia[d.date().isoformat()].append(item)
    if not por_dia:
        return []
    negativos = {dia: sum(1 for i in lista if _tom(i) == "negativo") for dia, lista in por_dia.items()}
    # a coleta cresceu ao longo do tempo: o pico é medido pela PROPORÇÃO de
    # negativas do dia, não pelo número absoluto
    proporcao = {dia: negativos[dia] / len(por_dia[dia]) for dia in por_dia if len(por_dia[dia]) >= 5}
    if not proporcao:
        return []
    valores = list(proporcao.values())
    media = sum(valores) / len(valores)
    desvio = math.sqrt(sum((v - media) ** 2 for v in valores) / len(valores))
    limite = max(media * 1.6, media + 1.5 * desvio)
    eventos = []
    for dia, prop in sorted(proporcao.items(), key=lambda kv: -kv[1]):
        neg = negativos[dia]
        if prop < limite:
            break
        if neg < 3:
            continue
        manchetes = [i for i in por_dia[dia] if _tom(i) == "negativo"]
        eventos.append(
            {
                "data": dia,
                "negativos": neg,
                "total": len(por_dia[dia]),
                "pct_negativas": round(100 * prop),
                "pct_normal": round(100 * media),
                "manchetes": [
                    {
                        "titulo": sem_veiculo(i.get("titulo", "")),
                        "veiculo": i.get("veiculo", ""),
                        "url": i.get("url", ""),
                    }
                    for i in manchetes[:3]
                ],
            }
        )
        if len(eventos) >= maximo:
            break
    return sorted(eventos, key=lambda e: e["data"], reverse=True)


def media_negativos(itens: list[dict], dias: int = 60) -> float:
    fim = max((d for d in (_data(i) for i in itens) if d), default=datetime.now(timezone.utc))
    inicio = (fim - timedelta(days=dias)).date()
    por_dia: Counter = Counter()
    for item in itens:
        d = _data(item)
        if d and d.date() >= inicio and _tom(item) == "negativo":
            por_dia[d.date().isoformat()] += 1
    return round(sum(por_dia.values()) / max(1, dias), 1)
