"""Extracao de frequencia de palavras para a nuvem interativa do dashboard.

Normaliza o texto (minusculas, sem acentos), remove stopwords em portugues e
ruido do RSS/HTML, e devolve os contadores globais e por mes.
"""

import re
import unicodedata
from collections import Counter, defaultdict

_STOPWORDS = {
    # portugues: funcionais e discursivas (baseada em NLTK pt + extensoes)
    "a", "à", "ao", "aos", "as", "às", "o", "os", "um", "uma", "uns", "umas",
    "de", "do", "dos", "da", "das", "em", "no", "nos", "na", "nas", "num",
    "numa", "nuns", "numas", "e", "ou", "que", "para", "por", "com", "sem",
    "sobre", "entre", "desde", "ate", "ate", "pelo", "pela", "pelos", "pelas",
    "como", "se", "mas", "mais", "menos", "tambem", "ja", "nao", "sim", "foi",
    "ser", "esta", "estao", "foram", "sao", "tem", "ter", "tinha", "tera",
    "ha", "havia", "vai", "vao", "ir", "era", "eram", "sendo", "diz", "disse",
    "afirma", "segundo", "ainda", "quando", "onde", "depois", "antes", "agora",
    "pos", "sera", "devem", "deve", "pode", "podem", "fazer", "fez", "nesta",
    "neste", "nessa", "nesse", "nestes", "nessas", "tudo", "nada", "todo",
    "todos", "toda", "todas", "outro", "outros", "outra", "outras", "mesmo",
    "mesma", "mesmos", "mesmas", "seus", "suas", "seu", "sua", "contra",
    "dentro", "fora", "perto", "longe", "tal", "tais", "cada", "qual", "quais",
    "quem", "cujo", "cujos", "cuja", "cujas", "durante", "mediante", "via",
    "lhe", "lhes", "eles", "elas", "ele", "ela", "nos", "vos", "eu", "tu",
    "te", "me", "mim", "meu", "minha", "meus", "minhas", "nosso", "nossa",
    "nossos", "nossas", "este", "esta", "isto", "isso", "aquele", "aquela",
    "aqueles", "aquelas", "aquilo", "aqui", "ali", "la", "pois", "portanto",
    "entao", "porem", "todavia", "contudo", "bem", "mal", "muito", "muitos",
    "muita", "muitas", "pouco", "poucos", "pouca", "poucas", "varios", "varias",
    "diversos", "diversas", "aproximadamente", "cerca", "apenas", "somente",
    "inclusive", "exclusive", "talvez", "atualmente", "hoje", "ontem", "amanha",
    "apos", "conforme", "ninguem", "algum", "alguns", "alguma", "algumas",
    "nenhum", "nenhuns", "nenhuma", "nenhumas", "qualquer", "quaisquer",
    "quando", "tanto", "tanta", "temos", "tenho", "tinham", "sera", "serao",
    "seriam", "era", "eram", "sou", "es", "somos", "saiba", "sabia", "saber",
    "sabe", "sei", "conhece", "conhecer", "vem", "viemos", "vira", "virao",
    "visto", "vista", "dado", "dada", "dados", "devido", "devida", "ligado",
    "ligada", "relacionado", "relacionada", "partir", "torna", "tornar",
    "tornou", "tornou-se", "passou", "passar", "volta", "voltar", "acima",
    "abaixo", "adiante", "atras", "atraves", "cima", "decima", "traz", "traz",
    # ruido do RSS/Google News
    "href", "target", "blank", "nbsp", "font", "color", "title", "div",
    "span", "class", "style", "src", "alt", "data", "br", "html", "body",
    "gt", "lt", "amp", "a", "ta", "www", "com", "http", "https", "news",
    "noticias", "noticia", "confira", "veja", "assista", "leia", "saiba",
    "materia", "materias", "artigo", "conteudo", "pagina", "clique",
    "acesse", "reporter", "redacao", "portal", "jornal", "g1",
    "video", "videos", "assista", "canal", "episodio", "programa", "musica",
    # termos politicos de baixo valor de analise
    "vereador", "vereadora", "vereadores", "vereadoras", "parlamentar",
    "parlamentares", "candidato", "candidata", "candidatos", "voto",
    "votos", "mandato", "legislatura", "plenario", "sessao", "pauta",
    "camara", "municipal", "prefeitura", "prefeito", "prefeita",
    "governo", "governador", "estado", "federal", "ministerio",
    "eleicoes", "eleicao", "eleitoral", "eleitorais", "cuiaba",
    "varzea", "mato", "grosso", "grossense", "mt", "brasil", "pais",
    "epoca", "nunca", "dai", "toda", "cada", "essa", "esse", "dessa",
    "desse", "nesse", "naquela", "naquele", "sempre", "tambem", "ainda",
    # nomes de veiculos/fontes (ruido para analise tematica)
"folhamax", "vgnoticias", "gazeta", "hipernoticias", "hipernoticias voce",
    "olhardireto", "olhar", "rdnews", "midianews", "g1", "midiajur",
    "diariodecuiaba", "estadao", "oglobo", "uol", "cnn", "poder360",
    "primeirapagina", "metropoles", "caldeirao", "circuitomt", "rdmonline",
    "mtplay", "mtagora", "newsmt", "repormatermt", "sapicua", "pocone",
    "portalviu", "oempallador", "bra1", "encom", "noveen",
    "leiaagora", "jbnews", "semana7", "momento", "vejabem", "fatos de",
    "noticiamax", "mtafato", "mteconomico", "conexaomt",
    "ponto na curva", "mtemfoco", "issoenoticia", "primeira hora",
    "tribuna", "folhadoestado", "folha de", "correio", "jovem", "pan",
    "esporte", "globonews", "cbn", "bandnews", "record", "sbt",
}

_RUIM_RE = re.compile(r"[^a-z0-9 ]")
_HEX_RE = re.compile(r"#?[0-9a-f]{6}\b")
_RSS_ARTEFATOS = (
    "font color", "a href target blank", "href=", "&nbsp;", "target=_blank",
    "clique aqui", "leia mais", "ver mais", "acompanhe", "participe",
)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    for artefato in _RSS_ARTEFATOS:
        t = t.replace(artefato, " ")
    t = _HEX_RE.sub(" ", t)
    t = _RUIM_RE.sub(" ", t)
    return t


def extrair_palavras(texto: str) -> list[str]:
    """Tokeniza um texto limpo, removendo stopwords e termos curtos."""
    t = _normalizar(texto)
    return [
        p for p in t.split()
        if len(p) >= 3
        and p not in _STOPWORDS
        and not p.isdigit()
        and not re.fullmatch(r"[0-9a-f]{6}", p)
    ]


def frequencia(clippings: list[dict], top: int = 150) -> tuple[dict, dict]:
    """Frequencia global e por mes (chave 'YYYY-MM') das palavras dos clippings."""
    geral: Counter = Counter()
    por_mes: defaultdict[str, Counter] = defaultdict(Counter)
    for c in clippings:
        palavras = extrair_palavras(c.get("texto_limpo") or "")
        geral.update(palavras)
        data = c.get("data_publicacao")
        if data is not None:
            mes = data.strftime("%Y-%m") if hasattr(data, "strftime") else str(data)[:7]
            por_mes[mes].update(palavras)
    return (
        dict(geral.most_common(top)),
        {mes: dict(cont.most_common(top)) for mes, cont in sorted(por_mes.items())},
    )