"""Testes da CHD de Reinert, do corpus IRaMuTeQ e do texto verificado.

Cobre:
  - corpus no formato do IRaMuTeQ (cabecalho `**** *variavel`, ST de ~40 formas);
  - lematizacao e exclusoes (siglas, numeros);
  - CHD do `rainette` sobre um corpus **sintetico com classes conhecidas**;
  - texto verificado: numero fora do grafo e palavra fora do grafo sao reprovados;
  - texto de modelo (template) como reserva.

Uso (a partir de `backend/`):
    python tests/teste_reinert.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from cerra_nucleo.processing import corpus_iramuteq, reinert, textos_graficos  # noqa: E402

PASSOU: list[str] = []
FALHOU: list[str] = []


def checar(desc: str, condicao: bool, extra: str = "") -> None:
    if condicao:
        PASSOU.append(desc)
        print(f"  PASS  {desc}")
    else:
        FALHOU.append(desc)
        print(f"  FAIL  {desc} {extra}")


# Corpus sintetico com 3 temas bem separados (saude / obras / transporte).
CORPUS_SINTETICO = [
    ("A UPA do bairro esta lotada e faltam profissionais de saude no atendimento.", "saude"),
    ("A unidade de saude atende pacientes com demora e falta de medicamentos.", "saude"),
    ("Profissionais de saude Criticam a falta de equipping nas unidades de saude.", "saude"),
    ("A prefeitura anunciou obra de asfalto na avenida e a construcao de uma ponte.", "obras"),
    ("O recapeamento de ruas e o saneamento sao prioridades da obra municipal.", "obras"),
    ("A obra de asfalto atrasou e o recapeamento das ruas ficou para depois.", "obras"),
    ("O onibus passa a cada quarenta minutos e o transito piorou na avenida.", "transporte"),
    ("Moradores reclamam do atraso do onibus e do transito na cidade.", "transporte"),
    ("A nova linha de transporte publico vai atender os bairros da cidade.", "transporte"),
]


def main() -> int:
    print("== corpus IRaMuTeQ ==")
    itens = [
        {
            "texto_limpo": texto,
            "agente_id": "fulano",
            "casa": "Camara Cuiaba",
            "plataforma": "Web",
            "tipo": "Noticia",
            "sentimento": "neutro",
            "semana": "2026w48",
        }
        for texto, _ in CORPUS_SINTETICO
    ]
    corpus = corpus_iramuteq.montar_corpus(itens)
    checar("9 itens no corpus", len(corpus) == 9, str(len(corpus)))

    cabecalho = corpus_iramuteq.cabecalho(corpus[0])
    checar("cabecalho com ****", cabecalho.startswith("****"), cabecalho)
    checar("variavel do agente", "*agente_fulano" in cabecalho, cabecalho)
    checar("variavel da casa", "*casa_Camara" in cabecalho, cabecalho)
    checar("variavel do sentimento", "*sent_neutro" in cabecalho, cabecalho)
    checar("variavel da semana", "*semana_2026w48" in cabecalho, cabecalho)

    est = corpus_iramuteq.estatisticas(corpus)
    checar("estatisticas com textos", est["textos"] == 9, str(est))
    checar("estatisticas com ST", est["st"] >= 9, str(est))
    checar("estatisticas com hapax", est["hapax"] > 0, str(est))

    lematizado = corpus_iramuteq.lematizar("As UPA's e os onibus da cidade")
    checar("sigla preservada", "upa" in lematizado, lematizado)
    checar("plural tirado", "onibu" in lematizado, lematizado)

    segmentos = corpus_iramuteq.segmentar("palavra " * 100, tamanho_st=40)
    checar("segmentos de ~40 formas", all(len(s.split()) <= 45 for s in segmentos), str(len(segmentos)))
    checar("texto curto vira 1 ST", len(corpus_iramuteq.segmentar("poucas palavras aqui")) == 1)

    limpo = corpus_iramuteq.limpar_texto("<p>Texto com @user e https://exemplo.com</p>")
    checar("HTML removido", "<p>" not in limpo, limpo)
    checar("URL removida", "https://" not in limpo, limpo)

    print("== CHD de Reinert (rainette) ==")
    checar("Rscript disponivel", reinert.rscript_disponivel())
    checar("rainette instalado", reinert.rainette_instalado())
    if not (reinert.rscript_disponivel() and reinert.rainette_instalado()):
        print("  (pulado: R/rainette ausente)")
    else:
        txt = corpus_iramuteq.exportar_txt(
            corpus, str(Path(__file__).resolve().parent / "_tmp_corpus.txt")
        )
        resultado = reinert.executar(Path(txt).read_text(encoding="utf-8"), k=3, min_segment_size=0, min_split_members=2)
        checar("CHD executada", resultado["ok"], resultado["erro"][:160])
        if resultado["ok"]:
            classes = resultado["classes"]
            checar("pelo menos 2 classes", len(classes) >= 2, str(len(classes)))
            soma = sum(c["pct"] for c in classes)
            checar("percentuais somam ~100", abs(soma - 100) < 6, str(soma))
            tem_chi2 = any(c["chi2"] > 0 for c in classes)
            checar("chi2 calculado", tem_chi2)
            tem_p = all(0 <= c["p"] <= 1 for c in classes)
            checar("p-value entre 0 e 1", tem_p)
            # O corpus sintetico tem 3 temas: as classes devem cite-los.
            formas = {f["f"] for c in classes for f in c["formas"]}
            temas = {"saude", "upa", "atendimento", "obra", "asfalto", "onibus", "transito"}
            achou = bool(formas & temas)
            checar("classes citam os temas do corpus", achou, str(sorted(formas))[:120])
            arvore = resultado["arvore"]
            checar("arvore com altura", bool(arvore.get("altura")))
        Path(Path(__file__).resolve().parent / "_tmp_corpus.txt").unlink(missing_ok=True)

    print("== texto verificado dos graficos ==")
    fatos = {
        "classes": [
            {
                "id": 1,
                "pct": 34.0,
                "forma": "saude",
                "formas": [{"f": "saude", "chi2": 45.2, "p": 0.001}, {"f": "upa", "chi2": 30.1, "p": 0.002}],
            },
            {
                "id": 2,
                "pct": 22.0,
                "forma": "obras",
                "formas": [{"f": "asfalto", "chi2": 25.0, "p": 0.01}],
            },
        ],
        "total": 412,
    }
    ok, problemas = textos_graficos.verificar(
        "Saude domina 34% da conversa, com 412 itens no periodo.", fatos
    )
    checar("texto com numeros do grafo aprovado", ok, str(problemas))

    ok2, problemas2 = textos_graficos.verificar(
        "A obra de asfalto dominou com 99.9% e a palavra 'xpto'.", fatos
    )
    checar("numero fora do grafo reprovado", not ok2)
    checar("problema do numero reportado", any("numero" in p for p in problemas2), str(problemas2))
    checar("problema da palavra reportado", any("palavra" in p for p in problemas2), str(problemas2))

    modelo = textos_graficos.texto_de_modelo(fatos, "grupos de assuntos")
    checar("texto de modelo gerado", "SAUDE" in modelo.upper(), modelo)
    checar("texto de modelo cita o total", "412" in modelo, modelo)

    print("== discurso ==")
    briefing = {
        "tese": "A prioridade da semana e a saude",
        "fatos": [
            {"id": "f1", "texto": "A UPA do Jardim America esta lotada", "fonte": "G1, 22/11"},
            {"id": "f2", "texto": "412 mencoes no periodo", "fonte": "Painel, 23/11"},
        ],
        "demandas_top": ["Demanda por mais profissionais de saude"],
    }
    fontes = textos_graficos.extrair_fontes(
        "A UPA esta lotada (G1, 22/11) e houve 412 mencoes (Painel, 23/11)."
    )
    checar("fontes extraidas", len(fontes) == 2, str(fontes))
    problemas_f = textos_graficos.verificar_fontes(
        "A UPA esta lotada (G1, 22/11).", briefing
    )
    checar("fonte conferida no briefing", not problemas_f, str(problemas_f))
    problemas_f2 = textos_graficos.verificar_fontes(
        "Isso veio de outro lugar (Folha, 10/10).", briefing
    )
    checar("fonte fora do briefing apontada", bool(problemas_f2), str(problemas_f2))

    print()
    print(f"RESULTADO: {len(PASSOU)} passaram, {len(FALHOU)} falharam")
    if FALHOU:
        for item in FALHOU:
            print("  FALHOU:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
