"""Testes do scraper de redes sociais via busca (sem rede, com dados simulados).

Cobre: mapeamento de dominio -> plataforma, dedup por URL, extracao de data
relativa, classificacao postagem x comentario e confianca.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from scraper import busca_social_scraper as bs  # noqa: E402

_total = 0
_falhas = 0


def check(nome: str, cond: bool, detalhe: str = "") -> None:
    global _total, _falhas
    _total += 1
    if cond:
        print(f"  PASS  {nome}")
    else:
        _falhas += 1
        print(f"  FAIL  {nome}  {detalhe}")


def teste_plataforma() -> None:
    print("== mapeamento de dominio -> plataforma ==")
    casos = {
        "https://www.instagram.com/p/abc/": "Instagram",
        "https://instagram.com/reel/xyz": "Instagram",
        "https://www.facebook.com/pagina/post/1": "Facebook",
        "https://m.facebook.com/story.php": "Facebook",
        "https://x.com/dep/status/1": "Twitter",
        "https://twitter.com/dep/status/1": "Twitter",
        "https://www.tiktok.com/@dep/video/1": "TikTok",
        "https://www.threads.net/@dep/post/1": "Threads",
        "https://www.kwai.com/@dep/video/1": "Kwai",
        "https://www.youtube.com/watch?v=1": "YouTube",
    }
    for url, esperado in casos.items():
        check(f"{url} -> {esperado}", bs.plataforma_da_url(url) == esperado, str(bs.plataforma_da_url(url)))
    check("dominio nao social -> None", bs.plataforma_da_url("https://www.globo.com/mt/noticia") is None)
    check("url invalida -> None", bs.plataforma_da_url("nao-e-url") is None)


def teste_comentario() -> None:
    print("== classificacao postagem x comentario ==")
    check("'comentou' => comentario", bs.parece_comentario("Maria comentou: adorei o projeto"))
    check("'comentários' => comentario", bs.parece_comentario("12 comentários nesta publicação"))
    check("'respondeu' => comentario", bs.parece_comentario("O deputado respondeu à seguidora"))
    check("'replying to' => comentario", bs.parece_comentario("Replying to @fulano: concordo"))
    check("post comum => postagem", not bs.parece_comentario("Novo projeto aprovado na ALMT"))
    check(
        "verbo de fala + citacao => comentario",
        bs.parece_comentario('Seguidor escreveu: “parabéns pelo trabalho”'),
    )
    check(
        "bio de perfil (on Instagram:) => postagem",
        not bs.parece_comentario('Janaina Riva on Instagram: "Presidente do MDB"'),
    )
    check("tipo de comentario", bs.classificar_tipo("Seguidor comentou", "muito bom") == "Comentario")
    check("tipo de postagem", bs.classificar_tipo("Agenda de hoje", "sessão na ALMT") == "Postagem")


def teste_data_relativa() -> None:
    print("== extracao de data relativa ==")
    agora = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
    d3 = bs.extrair_data_relativa("publicado há 3 dias", agora)
    check("'há 3 dias'", d3 is not None and abs((agora - d3) - timedelta(days=3)) < timedelta(minutes=1))
    h2 = bs.extrair_data_relativa("há 2 horas", agora)
    check("'há 2 horas'", h2 is not None and abs((agora - h2) - timedelta(hours=2)) < timedelta(minutes=1))
    ontem = bs.extrair_data_relativa("postado ontem", agora)
    check("'ontem'", ontem is not None and abs((agora - ontem) - timedelta(days=1)) < timedelta(minutes=1))
    check("sem data => None", bs.extrair_data_relativa("publicação oficial da ALMT", agora) is None)


def teste_confianca() -> None:
    print("== confianca da mencao ==")
    check("nome no snippet => alta", bs.calcular_confianca("Janaina Riva", "post", "Janaina Riva votou sim") == "alta")
    check("nome so no titulo => media/baixa",
          bs.calcular_confianca("Janaina Riva", "Janaina Riva no Instagram", "perfil oficial") in ("media", "baixa"))
    check("sem nome => baixa", bs.calcular_confianca("Fulano de Tal", "Noticia", "assunto generico") == "baixa")


def teste_dedup_e_coleta() -> None:
    print("== coleta simulada (dedup por URL + tipos) ==")
    simulados = [
        {"titulo": "Janaina Riva no Instagram", "url": "https://www.instagram.com/janainariva/",
         "snippet": "Janaina Riva publicou sobre a sessão. há 2 dias"},
        # URL repetida em outra consulta (deve ser deduplicada)
        {"titulo": "Janaina Riva no Instagram", "url": "https://www.instagram.com/janainariva/",
         "snippet": "repetido"},
        {"titulo": "Comentário de seguidor", "url": "https://www.facebook.com/p/1",
         "snippet": "Seguidor comentou: parabéns pelo trabalho"},
        {"titulo": "Notícia fora das redes", "url": "https://www.globo.com/mt/x",
         "snippet": "Janaina Riva"},
    ]
    sc = bs.BuscaSocialScraper({"rodizio": False, "max_consultas": 10, "max_resultados": 10})
    sc._consultar = lambda consulta, n: list(simulados)  # type: ignore[assignment]
    itens = sc.coletar({"id": "janaina-riva", "nome_urna": "Janaina Riva"}, limite=20)
    urls = [i.url for i in itens]
    check("URLs unicas (dedup)", len(urls) == len(set(urls)), str(urls))
    check("descarta dominio nao social", all("globo.com" not in u for u in urls))
    check("manteve Instagram e Facebook", {"Instagram", "Facebook"}.issubset({i.plataforma for i in itens}))
    check("comentario classificado", any(i.tipo == "Comentario" for i in itens))
    check("metadados de origem", all(i.metadados.get("origem_coleta") == "busca" for i in itens))
    check("data relativa extraida", any(i.metadados.get("data_estimada") is False for i in itens))


def main() -> None:
    teste_plataforma()
    teste_comentario()
    teste_data_relativa()
    teste_confianca()
    teste_dedup_e_coleta()
    print(f"\nRESULTADO: {_total - _falhas} passaram, {_falhas} falharam")
    sys.exit(1 if _falhas else 0)


if __name__ == "__main__":
    main()
