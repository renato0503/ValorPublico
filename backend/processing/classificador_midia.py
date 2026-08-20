"""Classifica cada clipping em uma categoria de midia.

Objetivo: destrinchar a origem "Web" (e demais plataformas) em categorias
compreensiveis para o share de midia do dashboard:

  Portal, Radio, TV, Jornal Impresso, Governo, Redes Sociais,
  YouTube, Telegram, Outros

A classificacao combina um mapa explicito de veiculos conhecidos (MT/local e
nacionais comuns) com heuristica por marcadores no nome/dominio.
"""

import re
from urllib.parse import urlparse

CAT_PORTAL = "Portal"
CAT_RADIO = "Radio"
CAT_TV = "TV"
CAT_JORNAL = "Jornal Impresso"
CAT_GOVERNO = "Governo"
CAT_REDES = "Redes Sociais"
CAT_YOUTUBE = "YouTube"
CAT_TELEGRAM = "Telegram"
CAT_OUTROS = "Outros"

# Veiculos explicitos -> categoria (mapeamento curado para precisao)
_VEICULOS_CONHECIDOS = {
    # --- Mato Grosso: portais ---
    "folhamax": CAT_PORTAL,
    "folhamax.com": CAT_PORTAL,
    "folhamax.com.br": CAT_PORTAL,
    "vgnoticias.com.br": CAT_PORTAL,
    "o bom da notícia": CAT_PORTAL,
    "olhar direto": CAT_PORTAL,
    "hipernotícias - você bem informado": CAT_PORTAL,
    "hipernotícias": CAT_PORTAL,
    "rdnews": CAT_PORTAL,
    "midianews": CAT_PORTAL,
    "primeira página": CAT_PORTAL,
    "o mato grosso": CAT_PORTAL,
    "noveen.com.br": CAT_PORTAL,
    "o documento": CAT_PORTAL,
    "novidades mt": CAT_PORTAL,
    "mt em foco": CAT_PORTAL,
    "isso é notícia": CAT_PORTAL,
    "notícia max": CAT_PORTAL,
    "fatos de mato grosso": CAT_PORTAL,
    "veja bem mt": CAT_PORTAL,
    "conexão mt": CAT_PORTAL,
    "sapicuá": CAT_PORTAL,
    "mato grosso mais": CAT_PORTAL,
    "mt de fato": CAT_PORTAL,
    "mt econômico": CAT_PORTAL,
    "ponto na curva": CAT_PORTAL,
    "caldeirão político": CAT_PORTAL,
    "circuitomt.com.br": CAT_PORTAL,
    "a bronca popular": CAT_PORTAL,
    "pnbonline.com.br": CAT_PORTAL,
    "mtagora.com.br": CAT_PORTAL,
    "baixada cuiabana news": CAT_PORTAL,
    "passandoalimpomt.com.br": CAT_PORTAL,
    "agora mt": CAT_PORTAL,
    "mt em foco": CAT_PORTAL,
    "agenda do poder": CAT_PORTAL,
    "repórtermt": CAT_PORTAL,
    "newsmt.com.br": CAT_PORTAL,
    "nx1.com.br": CAT_PORTAL,
    "poconet": CAT_PORTAL,
    "transmissão política": CAT_PORTAL,
    "o vetor": CAT_PORTAL,
    "cliquef5": CAT_PORTAL,
    "bra1.com.br": CAT_PORTAL,
    "midiajur.com.br": CAT_PORTAL,
    "en.com.br": CAT_PORTAL,
    "tempo real": CAT_PORTAL,
    "acesse política": CAT_PORTAL,
    "blogs do vg": CAT_PORTAL,
    "blog do valente": CAT_PORTAL,
    "blog braga": CAT_PORTAL,
    "blog do acélio": CAT_PORTAL,
    "claudio dantas": CAT_PORTAL,
    "edenevaldo alves": CAT_PORTAL,
    "portal do marcos santos": CAT_PORTAL,
    "mt esporte": CAT_PORTAL,
    # --- Mato Grosso: TV ---
    "tv centro américa": CAT_TV,
    "tv centro-america": CAT_TV,
    "tv ca": CAT_TV,
    "tv vila real": CAT_TV,
    "tv rondon": CAT_TV,
    "tv cuiabá": CAT_TV,
    "tvcuiaba": CAT_TV,
    "rdmonline.com.br": CAT_TV,
    "mt play": CAT_TV,
    "mtplay": CAT_TV,
    "rdm tv": CAT_TV,
    "tv rdm": CAT_TV,
    # --- Mato Grosso: radio ---
    "cbncuiaba.com.br": CAT_RADIO,
    "cbn": CAT_RADIO,
    "capital fm": CAT_RADIO,
    "centro américa fm": CAT_RADIO,
    "94fm": CAT_RADIO,
    "bandnews": CAT_RADIO,
    "sistema província de comunicação": CAT_RADIO,
    # --- Mato Grosso: jornais ---
    "diario de cuiabá": CAT_JORNAL,
    "gazeta digital": CAT_JORNAL,
    "folha do estado": CAT_JORNAL,
    "folhaestado.com.br": CAT_JORNAL,
    "o mato grosso": CAT_PORTAL,
    # --- Nacionais: jornais ---
    "estadão": CAT_JORNAL,
    "estadão mt": CAT_JORNAL,
    "o globo": CAT_JORNAL,
    "folha de s.paulo": CAT_JORNAL,
    "veja": CAT_JORNAL,
    "veja são paulo": CAT_JORNAL,
    "gazeta do povo": CAT_JORNAL,
    "gzh": CAT_JORNAL,
    "correio do povo": CAT_JORNAL,
    "a tribuna": CAT_JORNAL,
    "valor econômico": CAT_JORNAL,
    "diário gaúcho": CAT_JORNAL,
    "o tempo": CAT_JORNAL,
    "tribuna do paraná": CAT_JORNAL,
    "jornal grande bahia": CAT_JORNAL,
    "jornal opção": CAT_JORNAL,
    "jornal correio": CAT_JORNAL,
    "jornal oeste": CAT_JORNAL,
    "folha pe": CAT_JORNAL,
    "folha do sul": CAT_JORNAL,
    "folha dos lagos": CAT_JORNAL,
    "diário do rio": CAT_JORNAL,
    "diário do comércio": CAT_JORNAL,
    "correio da lavoura": CAT_JORNAL,
    "carta capital": CAT_JORNAL,
    "revista oeste": CAT_JORNAL,
    "revista fórum": CAT_JORNAL,
    "forbes brasil": CAT_JORNAL,
    "extra online": CAT_JORNAL,
    "a tarde": CAT_JORNAL,
    "público": CAT_JORNAL,
    "expresso": CAT_JORNAL,
    "gazeta de são paulo": CAT_JORNAL,
    "plural.jor.br": CAT_JORNAL,
    "jb litoral": CAT_JORNAL,
    "primeira hora": CAT_JORNAL,
    "tribuna de petrópolis": CAT_JORNAL,
    "jornal folha do progresso": CAT_JORNAL,
    "jornal extra de alagoas": CAT_JORNAL,
    "blogs.correiobraziliense.com.br": CAT_JORNAL,
    # --- Nacionais: TV ---
    "cnn brasil": CAT_TV,
    "sbt news": CAT_TV,
    "band.com.br": CAT_TV,
    "esporte": CAT_TV,
    "gshow": CAT_TV,
    "canal rural": CAT_TV,
    # --- Nacionais: radio ---
    "jovem pan": CAT_RADIO,
    "rádio itatiaia": CAT_RADIO,
    # --- Nacionais: portais ---
    "g1": CAT_PORTAL,
    "uol notícias": CAT_PORTAL,
    "uol": CAT_PORTAL,
    "uol economia": CAT_PORTAL,
    "metrópoles": CAT_PORTAL,
    "poder360": CAT_PORTAL,
    "congresso em foco": CAT_PORTAL,
    "consultor jurídico": CAT_PORTAL,
    "bha z": CAT_PORTAL,
    "infonet": CAT_PORTAL,
    "bahia notícias": CAT_PORTAL,
    "bahia sem fronteiras": CAT_PORTAL,
    "muita informação": CAT_PORTAL,
    "foco cidade": CAT_PORTAL,
    "plantão news": CAT_PORTAL,
    "última hora online": CAT_PORTAL,
    "midiamax": CAT_PORTAL,
    "tnh1": CAT_PORTAL,
    "amazonas atual": CAT_PORTAL,
    "radar amazônico": CAT_PORTAL,
    "bncamazonas.com.br": CAT_PORTAL,
    "portal miséria": CAT_PORTAL,
    "portalmt": CAT_PORTAL,
    "portal mato grosso": CAT_PORTAL,
    "pleno.news": CAT_PORTAL,
    "jota info": CAT_PORTAL,
    "neofeed": CAT_PORTAL,
    "money times": CAT_PORTAL,
    "leia agora": CAT_PORTAL,
    "leiagora": CAT_PORTAL,
    "notícia máxima": CAT_PORTAL,
    "o livre": CAT_PORTAL,
    "semana 7": CAT_PORTAL,
    "jbnews": CAT_PORTAL,
    "momento mt": CAT_PORTAL,
    "gc notícias": CAT_PORTAL,
    "içara news": CAT_PORTAL,
    "guaraí notícias": CAT_PORTAL,
    "paranaíba mais": CAT_PORTAL,
    "sudoeste bahia": CAT_PORTAL,
    "alagoas alerta": CAT_PORTAL,
    "folha z": CAT_PORTAL,
    "ng notícias": CAT_PORTAL,
    "expressão notícias": CAT_PORTAL,
    "francês news": CAT_PORTAL,
    "portalviu.com.br": CAT_PORTAL,
    "edestaquebrasilia.com.br": CAT_PORTAL,
    "poder goiás": CAT_PORTAL,
    "só notícias": CAT_PORTAL,
    "o empallador": CAT_PORTAL,
    "o fator": CAT_PORTAL,
    "topnews.com.br": CAT_PORTAL,
    "bahia economica": CAT_PORTAL,
    "cidadesnanet.com": CAT_PORTAL,
    "araguaia notícia": CAT_PORTAL,
    "estado político": CAT_PORTAL,
    "agência cenarium": CAT_OUTROS,
    "preto no branco | com sibelle fonseca": CAT_PORTAL,
    # --- Governo / oficiais ---
    "prefeitura municipal de várzea grande": CAT_GOVERNO,
    "prefeitura de cuiabá": CAT_GOVERNO,
    "tribunal de justiça do estado da bahia": CAT_GOVERNO,
    "câmara municipal de maceió": CAT_GOVERNO,
    "camara municipal de maceio": CAT_GOVERNO,
    "stf noticias": CAT_GOVERNO,
    "câmara municipal de sorocaba": CAT_GOVERNO,
    "prefeitura de belford roxo": CAT_GOVERNO,
    "prefeitura de manaus": CAT_GOVERNO,
    "secretaria municipal de educação": CAT_GOVERNO,
    "assembleia legislativa do estado de são paulo": CAT_GOVERNO,
    "câmara municipal de anápolis": CAT_GOVERNO,
    "tjpe": CAT_GOVERNO,
    "goias.gov": CAT_GOVERNO,
    "portal da alego": CAT_GOVERNO,
    "prefeitura de itabuna": CAT_GOVERNO,
    "prefeitura municipal de santa terezinha de itaipu": CAT_GOVERNO,
    "maraba.pa.gov.br": CAT_GOVERNO,
    "prefeitura municipal de luís eduardo magalhães": CAT_GOVERNO,
    "prefeitura municipal de vitória da conquista - pmvc": CAT_GOVERNO,
    "prefeitura de barreiras – ba": CAT_GOVERNO,
    "www.gov.br": CAT_GOVERNO,
    "ministério público do estado de mato grosso": CAT_GOVERNO,
    "câmara municipal de pouso alegre": CAT_GOVERNO,
    "defensoria pública do estado do amazonas": CAT_GOVERNO,
    "tjam.jus.br": CAT_GOVERNO,
    "prefeitura de salvador": CAT_GOVERNO,
    "prefeitura municipal de sorriso": CAT_GOVERNO,
    "defensoria pública do estado de mato grosso": CAT_GOVERNO,
    "prefeitura de anápolis": CAT_GOVERNO,
    "câmara municipal de uberlândia": CAT_GOVERNO,
    "prefeitura de cubatão": CAT_GOVERNO,
    # --- Redes sociais (quando vierem via Google News) ---
    "instagram.com": CAT_REDES,
    "facebook.com": CAT_REDES,
}

# Normaliza as chaves para minusculas (a busca usa o nome em lowercase).
_VEICULOS_CONHECIDOS = {k.lower(): v for k, v in _VEICULOS_CONHECIDOS.items()}

_MARCADOR_REDES = ("instagram.com", "facebook.com", "tiktok.com", "x.com", "twitter.com")
_MARCADOR_YOUTUBE = ("youtube.com", "youtu.be")
_MARCADOR_GOVERNO = (
    "prefeitura", "câmara municipal", "camara municipal", "tribunal", "ministério",
    "ministério público", "assembleia", "defensoria", "governo", "secom", "senado",
    "câmara", "camara", "jus.br", ".gov", "stf", "tjmt", "tjpe", "tjam",
)
_MARCADOR_RADIO = (
    " fm", "fm ", "fm.", "radio ", "rádio", "radiocapital", "radiotv", "webradio",
    " cbn", "bandnews", "jovem pan", "itatiaia", "band fm", "centro américa fm",
    "94 fm", "capital fm", "tupi",
)
_MARCADOR_TV = (
    "tv ", " tv", "canal ", "tvc", "rondontv", "rdm tv", "mt play", "mtplay",
    "sbt", "record", "redetv", "band tv", "cnn brasil", "globo", "gshow",
    "canal rural", "espn",
)
_MARCADOR_JORNAL = (
    "diario", "diário", "gazeta", "folha", "o globo", "estadão", "correio",
    "a tribuna", "valor econômico", "veja", "jornal", "tribuna", "publico",
    "expresso", "revista", "forbes", "extra",
)


def extrair_dominio(url: str) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""


def classificar_midia(veiculo: str, url: str = "") -> str:
    """Classifica um veiculo/fonte em uma categoria de midia."""
    nome = (veiculo or "").strip().lower()
    dominio = extrair_dominio(url)
    texto = f"{nome} {dominio}"

    if not nome and not dominio:
        return CAT_OUTROS

    if nome in _VEICULOS_CONHECIDOS:
        return _VEICULOS_CONHECIDOS[nome]
    if dominio in _VEICULOS_CONHECIDOS:
        return _VEICULOS_CONHECIDOS[dominio]

    if any(m in texto for m in _MARCADOR_REDES):
        return CAT_REDES
    if any(m in texto for m in _MARCADOR_YOUTUBE):
        return CAT_YOUTUBE
    if any(m in texto for m in _MARCADOR_GOVERNO):
        return CAT_GOVERNO
    if any(m in texto for m in _MARCADOR_RADIO):
        return CAT_RADIO
    if any(m in texto for m in _MARCADOR_TV):
        return CAT_TV
    if any(m in texto for m in _MARCADOR_JORNAL):
        return CAT_JORNAL
    return CAT_PORTAL


def classificar_clipping(clip: dict) -> str:
    """Classifica um clipping do Firestore (plataforma + metadados) em categoria."""
    plataforma = clip.get("plataforma", "Web")
    if plataforma == "Web":
        md = clip.get("metadados") or {}
        veiculo = md.get("veiculo") or clip.get("autor", "")
        return classificar_midia(veiculo, clip.get("url", ""))
    if plataforma in ("Twitter", "Instagram", "Facebook", "TikTok"):
        return CAT_REDES
    if plataforma == "YouTube":
        return CAT_YOUTUBE
    if plataforma == "Telegram":
        return CAT_TELEGRAM
    if plataforma == "TV":
        return CAT_TV
    if plataforma == "Radio":
        return CAT_RADIO
    if plataforma == "Impresso":
        return CAT_JORNAL
    return CAT_PORTAL