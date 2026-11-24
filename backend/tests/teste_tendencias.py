"""Testes das tendencias, do indice de crise e da previsao (E1 do plano 15).

Cobre:
  - RSS do Google Trends (parser com XML de exemplo, sem rede);
  - regra do pico de atencao;
  - indice de crise (K-28): z-score, limiar e mensagens;
  - previsao (K-33) com serie sintetica;
  - agregacao de series e limites de tamanho.

Uso (a partir de `backend/`):
    python tests/teste_tendencias.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from cerra_nucleo.processing.indicadores import (  # noqa: E402
    agrupar_por_dia,
    indice_crise,
    projetar,
    resumo_projeccao,
)
from cerra_nucleo.scraper.tendencias import (  # noqa: E402
    _parse_rss_trends,
    pico_de_atencao,
)

PASSOU: list[str] = []
FALHOU: list[str] = []

RSS_EXEMPLO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item>
      <title>ponte do rio niteroi</title>
      <ht:approx_traffic>1000+</ht:approx_traffic>
      <link>https://trends.google.com/trending/rss?geo=BR-MT</link>
      <ht:news_item>
        <ht:news_item_title>Governo anuncia obra da ponte</ht:news_item_title>
        <ht:news_item_url>https://g1.globo.com/mt/mato-grosso/noticia/ponte.ghtml</ht:news_item_url>
        <ht:news_item_source>G1</ht:news_item_source>
      </ht:news_item>
    </item>
    <item>
      <title>a fazenda 18 enquete</title>
      <ht:approx_traffic>2000+</ht:approx_traffic>
      <link>https://trends.google.com/trending/rss?geo=BR-MT</link>
    </item>
  </channel>
</rss>
"""


def checar(desc: str, condicao: bool, extra: str = "") -> None:
    if condicao:
        PASSOU.append(desc)
        print(f"  PASS  {desc}")
    else:
        FALHOU.append(desc)
        print(f"  FAIL  {desc} {extra}")


def main() -> int:
    print("== RSS do Google Trends ==")
    itens = _parse_rss_trends(RSS_EXEMPLO)
    checar("dois itens no feed", len(itens) == 2, str(len(itens)))
    checar("termo lido", itens[0]["termo"] == "ponte do rio niteroi", str(itens[0]))
    checar("volume lido", itens[0]["volume"] == "1000+", str(itens[0]["volume"]))
    checar("noticia ligada", len(itens[0]["noticias"]) == 1)
    checar("fonte da noticia", itens[0]["noticias"][0]["fonte"] == "G1")
    checar("url da noticia", "g1.globo.com" in itens[0]["noticias"][0]["url"])

    print("== pico de atencao (K-32) ==")
    serie = [{"data": f"2026-11-{dia:02d}", "valor": 10} for dia in range(1, 20)]
    serie.append({"data": "2026-11-20", "valor": 60})
    pico = pico_de_atencao(serie)
    checar("pico detectado", pico["ativo"] is True, str(pico))
    checar("fator calculado", pico["fator"] >= 3, str(pico))
    serie_plana = [{"data": f"2026-11-{dia:02d}", "valor": 10} for dia in range(1, 20)]
    checar("sem pico na serie normal", pico_de_atencao(serie_plana)["ativo"] is False)
    checar("serie curta nao quebra", pico_de_atencao([])["ativo"] is False)

    print("== indice de crise (K-28) ==")
    serie_neg = {f"2026-11-{dia:02d}": 2 for dia in range(1, 26)}
    serie_neg["2026-11-24"] = 14
    crise = indice_crise(serie_neg)
    checar("crise ativa", crise["ativo"] is True, str(crise))
    checar("z-score acima de 3", crise["z"] >= 3, str(crise["z"]))
    # A janela de 24 h soma o dia de hoje e a parte final do dia anterior.
    checar(
        "negativos de 24 h contados",
        crise["negativos_24h"] == 16,
        str(crise["negativos_24h"]),
    )
    checar("media base calculada", crise["media_base"] > 0)
    checar("mensagem para o leigo", "negativos" in crise["mensagem"].lower(), crise["mensagem"])
    checar("fator calculado", crise["fator"] > 1)
    checar("z-score finito", abs(crise["z"]) < 1000, str(crise["z"]))

    serie_normal = {f"2026-11-{dia:02d}": 2 for dia in range(1, 26)}
    normal = indice_crise(serie_normal)
    checar("sem crise no normal", normal["ativo"] is False, str(normal))
    checar("serie vazia nao quebra", indice_crise({})["ativo"] is False)
    checar("sem historico avisa", "historico" in indice_crise({})["mensagem"].lower())

    print("== previsao (K-33) ==")
    serie_mencao = {f"2026-11-{dia:02d}": 10 + (dia % 5) for dia in range(1, 29)}
    resultado = projetar(serie_mencao)
    checar("projecao gerada", bool(resultado["previsao"]), str(resultado.get("erro"))[:80])
    checar("28 dias projetados", len(resultado["previsao"]) == 28, str(len(resultado["previsao"])))
    checar("faixa de 80% presente", all(
        p["inferior"] <= p["valor"] <= p["superior"] for p in resultado["previsao"]
    ))
    checar("metodo registrado", resultado["metodo"] in ("statsforecast", "prophet"))
    checar("historico preservado", len(resultado["historico"]) == 28)
    resumo = resumo_projeccao(resultado)
    checar("resumo curto e honesto", "projecao" in resumo.lower() and "promessa" in resumo.lower(), resumo)
    checar("serie curta avisada", projetar({"2026-11-01": 1})["previsao"] == [])

    print("== agregacao por dia ==")
    itens = [
        {"data_publicacao": "2026-11-20"},
        {"data_publicacao": "2026-11-20"},
        {"data_publicacao": "2026-11-21"},
        {"data_publicacao": ""},
        {"data_publicacao": "invalido"},
    ]
    contagem = agrupar_por_dia(itens)
    checar("contagem por dia", contagem.get("2026-11-20") == 2, str(contagem))
    checar("data invalida ignorada", len(contagem) == 2, str(contagem))

    print()
    print(f"RESULTADO: {len(PASSOU)} passaram, {len(FALHOU)} falharam")
    if FALHOU:
        for item in FALHOU:
            print("  FALHOU:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
