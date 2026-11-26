"""Refaz a análise do discurso (IRaMuTeQ/CHD) do Governo de MT da semana (plano 22, S0).

Atualiza SÓ `relatorio_semanal/<escopo>__<semana>` dos três escopos do Governo
(o Governo inteiro, o governador e o interino). O discurso da semana
(`discurso_semanal`) e a simulação NÃO são tocados.

Base: a união das coletas do Governo (sem veículos de fora de MT), últimos N
dias. Os textos dos gráficos saem de regras fixas a partir das classes
(sem LLM), em português simples e só com números do próprio resultado.

Uso (a partir de `backend/`):
    python scripts/refazer_analise_governo.py --sem-firestore   # só arquivos locais
    python scripts/refazer_analise_governo.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.processing import corpus_iramuteq, reinert  # noqa: E402
from config import settings  # noqa: E402
from processing.governo_filtros import linhas_da_base, sanear_itens  # noqa: E402
from processing.lexico import exemplos_por_palavras, explicar, legiveis, relevante  # noqa: E402
from scripts.semanal.relatorio import montar_relatorio, semana_atual  # noqa: E402

PASTA = Path(settings.DATA_DIR) / "governo_mt"
ESCOPOS = {
    "casa-governo-mt": ("casa", "Governo do Estado de Mato Grosso", ""),
    "agente-governador-otaviano-pivetta": ("agente", "Governador do Estado de Mato Grosso", "governador"),
    "agente-interino-max-russi": ("agente", "Governador Interino de Mato Grosso", "interino"),
}


def _pct(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def _palavras(classe: dict, n: int = 5) -> str:
    formas = [f.get("legivel") or f["f"] for f in classe.get("formas", []) if relevante(f["f"])][:n]
    return ", ".join(formas[:-1]) + (" e " + formas[-1] if len(formas) > 1 else (formas[0] if formas else ""))


def enriquecer(chd: dict, titulos: list[str]) -> None:
    """Nome, explicação e manchetes de exemplo de cada grupo (para leigos)."""
    for classe in chd.get("classes", []):
        palavras = [f["f"] for f in classe.get("formas", [])]
        exemplos = exemplos_por_palavras(palavras, titulos, n=3)
        desc = explicar(palavras, float(classe.get("pct", 0)), exemplos, titulos)
        classe.update(desc)
        classe["exemplos"] = exemplos
        mapa = legiveis(palavras[:12], titulos)
        for forma in classe.get("formas", []):
            forma["legivel"] = mapa.get(forma["f"], forma["f"])


def textos_dos_graficos(chd: dict, est: dict, dias: int, rotulo: str) -> dict:
    """Textos em linguagem simples, só com os números da própria análise."""
    classes = sorted(chd.get("classes", []), key=lambda c: -float(c.get("pct", 0)))
    if not classes:
        aviso = "Não houve texto suficiente para separar grupos de assunto neste período."
        return {k: aviso for k in ("resumo", "chd", "afc", "similitude", "especificidades", "sentimento")}
    maior = classes[0]
    relevantes = [c for c in classes if float(c["pct"]) >= 8]
    pontuais = [c for c in classes if float(c["pct"]) < 2]
    resumo = (
        f"Nos últimos {dias} dias, {est.get('textos', 0)} notícias sobre {rotulo[0].lower() + rotulo[1:]} "
        f"foram separadas em {len(classes)} assuntos. O que mais aparece é {maior['nome']} "
        f"({_pct(maior['pct'])} dos trechos)."
    )
    if len(relevantes) > 1:
        resumo += " Também pesam: " + "; ".join(
            f"{c['nome']} ({_pct(c['pct'])})" for c in relevantes[1:4]
        ) + "."
    if pontuais:
        resumo += (
            f" Há ainda {len(pontuais)} pautas pontuais (menos de 2% cada), como "
            + " e ".join(c["nome"] for c in pontuais[:2]) + "."
        )
    resumo += (
        " Leitura para a Secom: os assuntos grandes são a agenda que a imprensa já associa ao Governo; "
        "os pontuais são oportunidades (ou riscos) que ainda não viraram pauta."
    )
    chd_txt = (
        "Como funciona: o sistema lê os trechos das notícias e junta os que usam as mesmas palavras. "
        "Cada grupo é um assunto; a porcentagem diz quanto do noticiário ele ocupa. "
        + " ".join(
            f"{i}) {c['nome']} — {_pct(c['pct'])}." for i, c in enumerate(classes, 1)
        )
    )
    afc = (
        "O mapa coloca perto as palavras que aparecem juntas nos mesmos trechos: palavras vizinhas falam "
        f"do mesmo assunto. {maior['nome']} fica no centro por ser o mais frequente."
    )
    if pontuais:
        afc += (
            " Assuntos pequenos, como " + " e ".join(c["nome"] for c in pontuais[:2])
            + ", ficam nas bordas: são pautas pontuais."
        )
    similitude = (
        "A rede liga as palavras que mais aparecem juntas. Os nós do centro são os temas que puxam o "
        f"noticiário; neste período o centro é {_palavras(maior, 3)}."
    )
    especificidades = (
        "Mostra as palavras próprias de cada assunto, as que quase só aparecem nele. Servem para achar "
        f"a pauta de cada grupo: em {classes[min(1, len(classes) - 1)]['nome']}, por exemplo, "
        f"{_palavras(classes[min(1, len(classes) - 1)], 3)}."
    )
    sentimento = (
        "O tom de cada assunto vem das notícias que o compõem (positivo, neutro ou negativo). "
        "Assuntos com muitas notícias negativas pedem atenção da Secom."
    )
    return {
        "resumo": resumo,
        "chd": chd_txt,
        "afc": afc,
        "similitude": similitude,
        "especificidades": especificidades,
        "sentimento": sentimento,
    }


def itens_do_escopo(base: list[dict], alvo: str, dias: int) -> list[dict]:
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    saida = []
    for item in base:
        data = item.get("data")
        try:
            dt = datetime.fromisoformat(str(data).replace("Z", "+00:00")) if data else None
        except ValueError:
            dt = None
        if dt is None or dt < limite:
            continue
        if alvo and alvo not in (item.get("alvos") or []):
            continue
        saida.append(
            {
                "texto": f"{item.get('titulo', '')}. {item.get('resumo') or ''}",
                "veiculo": item.get("veiculo", ""),
                "agente_id": "governo-mt",
                "casa": "Governo MT",
                "plataforma": "Web",
                "tipo": "Noticia",
                "sentimento": item.get("sentimento", ""),
                "data": str(data or ""),
            }
        )
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dias", type=int, default=60)
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    base, removidos = sanear_itens(linhas_da_base(PASTA))
    print(f"base do Governo: {len(base)} notícias ({len(removidos)} de fora de MT ignoradas)")
    semana = semana_atual()
    pasta = Path(settings.DATA_DIR) / "semanal" / semana
    pasta.mkdir(parents=True, exist_ok=True)

    db = None
    if not args.sem_firestore:
        from core.firebase_client import init_firebase

        db = init_firebase()

    for escopo, (nivel, rotulo, alvo) in ESCOPOS.items():
        itens = itens_do_escopo(base, alvo, args.dias)
        corpus = corpus_iramuteq.montar_corpus(itens)
        if len(corpus) < 20:
            print(f"{escopo}: corpus pequeno ({len(corpus)}), pulado")
            continue
        est = corpus_iramuteq.estatisticas(corpus)
        caminho = pasta / f"corpus-{escopo}.txt"
        corpus_iramuteq.exportar_txt(corpus, str(caminho))
        # noticias sao curtas (titulo + resumo): com corpus grande, mais classes e
        # segmentos menores separam os assuntos; sem isso um grupo engole 95%
        if len(corpus) >= 1000:
            parametros = {"k": 10, "min_segment_size": 5, "min_split_members": 5}
        else:
            parametros = {"k": 6}
        chd = reinert.executar(caminho.read_text(encoding="utf-8"), **parametros)
        if not chd.get("ok"):
            print(f"{escopo}: CHD falhou ({chd.get('erro', '')[:100]}), nada gravado")
            continue
        titulos = [i["texto"].split(". ")[0] for i in itens]
        enriquecer(chd, titulos)
        relatorio = montar_relatorio(
            escopo, nivel, rotulo, chd, est, textos_dos_graficos(chd, est, args.dias, rotulo)
        )
        # o relatorio guarda o nome do assunto, a explicacao e as manchetes de exemplo
        por_id = {c["id"]: c for c in chd["classes"]}
        for classe in relatorio["chd"]["classes"]:
            origem = por_id.get(classe["id"], {})
            classe["rotulo"] = origem.get("nome") or classe["rotulo"]
            classe["tema"] = origem.get("tema", "")
            classe["explicacao"] = origem.get("explicacao", "")
            classe["st_tipicos"] = origem.get("exemplos", [])
            classe["formas"] = [f for f in classe["formas"] if relevante(f["f"])][:10]
        relatorio["orgao"] = "governo-mt"
        relatorio["periodo_dias"] = args.dias
        relatorio["base"] = "uniao das coletas do Governo, sem veiculos de fora de MT"
        (pasta / f"relatorio-{escopo}.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{escopo}: {len(corpus)} textos, {len(chd['classes'])} classes")
        for c in relatorio["chd"]["classes"]:
            print(f"    {c['pct']:5.1f}%  {c['rotulo']}")
        if db is not None:
            db.collection("relatorio_semanal").document(f"{escopo}__{semana}").set(relatorio)
            print(f"    gravado em relatorio_semanal/{escopo}__{semana}")
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "refazer_analise_governo"))
