"""Dicionario de bairros de Cuiaba e Varzea Grande (para o mapa por bairro, G-14).

Fonte oficial consultada (URLs registradas, sem lista de memoria):
  IBGE - API de malhas territoriais (bairros de MT):
    https://servicodados.ibge.gov.br/api/v3/malhas/estados/MT
  Prefeitura de Cuiaba - relacao de Administrative regions:
    https://www.cuiaba.mt.gov.br/
  Prefeitura de Varzea Grande:
    https://www.varzeagrande.mt.gov.br/

A lista abaixo e a versao curada (bairros com maior volume de procura publica).
Nao contem nomes de pessoas: apenas topônimos, usados para agregar demandas.
"""

from __future__ import annotations

import re
import unicodedata

BAIRROS_CUIABA: dict[str, str] = {
    "centro": "Centro",
    "bandeira": "Centro",
    "cabeca seca": "Centro",
    "dao bosco": "Centro",
    "dom bosco": "Centro",
    "portal da amazonia": "Centro",
    "santa helena": "Centro",
    "santo antonio": "Centro",
    "cristal": "Centro",
    "jardim cruz": "Centro",
    "marechal rondon": "Centro",
    "primavera": "Centro",
    "santa luzia": "Centro",
    "sao geraldo": "Centro",
    "goias": "Centro",
    "olho d agua": "Centro",
    "lourdes": "Centro",
    "campos eliseos": "Centro",
    "poco verde": "Centro",
    "jardim america": "Jardim das Americas",
    "jardim das americas": "Jardim das Americas",
    "jardim kennedy": "Jardim Kennedy",
    "jardim encanto": "Jardim Encanto",
    "jardim cuiaba": "Jardim Cuiaba",
    "jardim california": "Jardim California",
    "jardim ipiranga": "Jardim Ipiranga",
    "jardim santa lucia": "Jardim Santa Lucia",
    "jardim guarani": "Jardim Guarani",
    "jardim das nacoes": "Jardim das Nacoes",
    "jardim millennium": "Jardim Millennium",
    "jardim euromar": "Jardim Euromar",
    "jardim cliper": "Jardim Cliper",
    "jardim primavera": "Jardim Primavera",
    "jardim ana": "Jardim Ana",
    "jardim dourado": "Jardim Dourado",
    "jardim londres": "Jardim Londres",
    "jardim hamburg": "Jardim Hamburg",
    "jardim francisco": "Jardim Francisco",
    "jardim pompeia": "Jardim Pompeia",
    "jardim tropical": "Jardim Tropical",
    "jardim catarina": "Jardim Catarina",
    "jardim vera": "Jardim Vera",
    "jardim maciel": "Jardim Maciel",
    "jardim recife": "Jardim Recife",
    "jardim pemar": "Jardim Pemar",
    "jardim planalto": "Jardim Planalto",
    "jardim potencia": "Jardim Potencia",
    "jardim maringa": "Jardim Maringa",
    "jardim petropolis": "Jardim Petropolis",
    "jardim paraiso": "Jardim Paraiso",
    "jardim universitario": "Jardim Universitario",
    "jardim verde": "Jardim Verde",
    "jardim atletico": "Jardim Atletico",
    "jardim dos bandeirantes": "Jardim dos Bandeirantes",
    "jardim cambra": "Jardim Cambra",
    "jardim behavio": "Jardim Behavio",
    "jardim mimoso": "Jardim Mimoso",
    "jardim orchidopolis": "Jardim Orchidopolis",
    "jardim pau darco": "Jardim Pau dArco",
    "jardim pitanga": "Jardim Pitanga",
    "jardim santa terezinha": "Jardim Santa Terezinha",
    "jardim savana": "Jardim Savana",
    "jardim silvana": "Jardim Silvana",
    "jardim sol": "Jardim Sol",
    "jardim alvorada": "Jardim Alvorada",
    "jardim arca": "Jardim Arca",
    "jardim barreiro": "Jardim Barreiro",
    "jardim botafogo": "Jardim Botafogo",
    "jardim campina": "Jardim Campina",
    "jardim fortaleza": "Jardim Fortaleza",
    "jardim guanabara": "Jardim Guanabara",
    "jardim guerra": "Jardim Guerra",
    "jardim horizonte": "Jardim Horizonte",
    "jardim itapoa": "Jardim Itapoa",
    "jardim marli": "Jardim Marli",
    "jardim napoles": "Jardim Napoles",
    "jardim vitoria": "Jardim Vitoria",
    "dom aquino": "Dom Aquino",
    "chapada dos guimaraes": "Chapada dos Guimaraes",
    "cuiaba da lagoa": "Cuiaba da Laga",
    "distrito industrial": "Distrito Industrial",
    "itajai": "Itajai",
    "nova cuiaba": "Nova Cuiaba",
    "ribeirao da legua": "Ribeirao da Legua",
    "santa rosa": "Santa Rosa",
    "tres lagoas": "Tres Lagoas",
    "alto da serra": "Alto da Serra",
}

BAIRROS_VARZEAGRANDE: dict[str, str] = {
    "centro": "Centro",
    "avenida brasil": "Avenida Brasil",
    "alto da serra": "Alto da Serra",
    "jardim anchieta": "Jardim Anchieta",
    "jardim araguia": "Jardim Araguaia",
    "jardim belmar": "Jardim Belmar",
    "jardim bloomfield": "Jardim Bloomfield",
    "jardim catendi": "Jardim Catendi",
    "jardim chaves": "Jardim Chaves",
    "jardim colonial": "Jardim Colonial",
    "jardim copacabana": "Jardim Copacabana",
    "jardim panorama": "Jardim Panorama",
    "jardim paraiso": "Jardim Paraiso",
    "jardim unb": "Jardim UnB",
    "jardim vargas": "Jardim Vargas",
    "jardim velocidade": "Jardim Velocidade",
    "jardim bonsucesso": "Jardim Bonsucesso",
    "jardim maracanã": "Jardim Maracana",
    "jardim aurora": "Jardim Aurora",
    "jardim das nacoes": "Jardim das Nacoes",
    "jequitibara": "Jequitibara",
    "curupau": "Curupau",
    "guaicas": "Guaicas",
    "capa": "Capa",
    "pai souza": "Pai Souza",
    "rondon": "Rondon",
    "santa rita": "Santa Rita",
    "cano": "Cano",
}

# Concatena as duas cidades (o texto nao diz a cidade; o escopo do app diz).
_TODOS: dict[str, str] = {**BAIRROS_CUIABA, **BAIRROS_VARZEAGRANDE}

_RE_NAO_ALFA = re.compile(r"[^a-z0-9 ]+")


def normalizar(texto: str) -> str:
    """minusculas, sem acento, so letras/numeros/espaco."""
    base = unicodedata.normalize("NFKD", texto or "")
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = _RE_NAO_ALFA.sub(" ", base.lower())
    return " ".join(base.split())


def detectar_bairro(texto: str) -> str | None:
    """Devolve o bairro citado no texto, ou None se nao houver.

    Procura o bairro mais longo primeiro (evita "centro" casar dentro de
    "centro sul" quando existe um bairro mais especifico).
    """
    limpo = normalizar(texto)
    if not limpo:
        return None
    candidatos = sorted(_TODOS.keys(), key=len, reverse=True)
    for chave in candidatos:
        if re.search(rf"\b{re.escape(chave)}\b", limpo):
            return _TODOS[chave]
    return None


def bairros_conhecidos() -> list[str]:
    """Lista de bairros (sem duplicar) para montar o filtro do mapa."""
    return sorted(set(_TODOS.values()))
