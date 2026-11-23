"""Radar de propaganda publica / institucional (modulo "Radar" das plataformas
de clipping institucional).

Distingue o que e MATERIA JOURNALISTICA do que e PUBLICIDADE DE PODER PUBLICO
(propaganda institucional, publicidade de utilidade publica, publication
official), porque o radar serve para dois objetivos diferentes:

  1. TRANSPARENCIA: mostrar quem veiculou o que, quando e por quanto.
  2. SEGURANCA JURIDICA: prover prova/link do veiculo e detectar uso de
     simbologia publica (que, em campanha, e crime - art. 40 da Lei 9.504).

Classificacao retornada:
    classe  "propaganda_publica" | "materia_journalistica" | "indeterminada"
    orgao   "camara" | "prefeitura" | "governo" | "tribunal" | "orgao_federal" | ""
    tipo    "institucional" | "utilidade_publica" | "oficial" | "licitacao" |
            "campanha" | "publicidade" | ""
    simbolos_publicos bool  (usa simbolo de orgao publico)
    valor_publico_estimate float (quando houver base de valoracao)
"""

import re
import unicodedata

CLASSE_PROPAGANDA = "propaganda_publica"
CLASSE_JORNALISTICA = "materia_journalistica"
CLASSE_INDETERMINADA = "indeterminada"
# Publicacao vinda de um canal oficial (prefeitura, camara, diario oficial,
# secretaria do estado): e o objeto do radar, mesmo que o texto nao pareca
# propaganda (ex.: uma noticia institucional que-nao-e-anuncio).
CLASSE_PUBLICACAO_OFICIAL = "publicacao_oficial"

# Sinais de publicidade institucional
_RE_INSTITUCIONAL = re.compile(
    r"\b(propaganda institucional|publicidade institucional|campanha institucional|"
    r"publicidade de utilidade p[úu]blica|utilidade p[úu]blica|"
    r"campanha de awareness|divulga[çc][ãa]o institucional|"
    r"pe[çc]a d[ée]的宣传|pe[çc]a de propaganda)\b",
    re.IGNORECASE,
)
# Sinais de veiculacao oficial
_RE_OFICIAL = re.compile(
    r"\b(di[áa]rio oficial|d[oó]e\b|di[áa]rio oficial dos munic[ií]pios|"
    r"portaria|decreto|lei municipal|lei estadual|ato oficial|"
    r"publica[çc][ãa]o oficial|expediente|ata da sess[ãa]o|"
    r"relat[óo]rio de gest[ãa]o|prestação de contas|prestacao de contas)\b",
    re.IGNORECASE,
)
# Sinais de licitacao/contrato (transparencia do gasto)
_RE_LICITACAO = re.compile(
    r"\b(licita[çc][ãa]o|preg[ãa]o eletr[ôo]nico|tomada de pre[çc]os|"
    r"contrato administrativo|dispensa de licita[çc][ãa]o|credenciamento)\b",
    re.IGNORECASE,
)
# Sinais de midia paga (nao institucional, mas relevante para o radar)
_RE_MIDIA_PAGA = re.compile(
    r"\b(patroc[íi]nio|patrocinad[oa]|an[úu]ncio|propaganda de produto|"
    r"comercial|publicidade de empresa|merchandising)\b",
    re.IGNORECASE,
)
# Orgao emissor
_RE_ORGAOS = {
    "camara": re.compile(
        r"\b(c[âa]mara municipal|c[âa]mara de vereadores|c[âa]mara|vereadores?|"
        r"vereadoras?|comiss[ãa]o|plen[áa]rio|mesa diretora)\b",
        re.IGNORECASE,
    ),
    "prefeitura": re.compile(
        r"\b(prefeitura|secretaria municipal|secretaria de \w+)\b", re.IGNORECASE
    ),
    "governo": re.compile(
        r"\b(governo do estado|secretaria de estado|governador\w*)\b", re.IGNORECASE
    ),
    "tribunal": re.compile(
        r"\b(tribunal|magistratura|ju[íi]zo|minist[eé]rio p[úu]blico)\b", re.IGNORECASE
    ),
    "orgao_federal": re.compile(
        r"\b(governo federal|minist[eé]rio \w+|congresso nacional|"
        r"senado federal|c[âa]mara dos deputados|supremo tribunal)\b",
        re.IGNORECASE,
    ),
}
# Simbolos publicos (art. 40 da Lei 9.504)
_RE_SIMBOLOS = re.compile(
    r"\b(bras[aã]o|escudo (do|de) \w+|bandeira (do|de) \w+|"
    r"logotipo (da|do) (prefeitura|governo|c[âa]mara)|"
    r"maquina do estado|carro oficial|pal[aá]cio do governo)\b",
    re.IGNORECASE,
)


def _norm(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


# Órgão emissor deduzido pelo domínio da fonte (quando o texto não cita o órgão)
ORGAO_POR_DOMINIO = {
    "cuiaba.mt.gov.br": "prefeitura",
    "varzeagrande.mt.gov.br": "prefeitura",
    "camaracuiaba.mt.gov.br": "camara",
    "camaravarzeagrande.mt.gov.br": "camara",
    "cmvg.mt.gov.br": "camara",
    "secom.mt.gov.br": "governo",
    "iomat.mt.gov.br": "governo",
    "transparencia.mt.gov.br": "governo",
    "transparencia.cuiaba.mt.gov.br": "prefeitura",
    "cge.mt.gov.br": "governo",
    "legislacao.mt.gov.br": "governo",
    "mt.gov.br": "governo",
}


def orgao_por_dominio(dominio: str) -> str:
    """Deduz o órgão emissor a partir do domínio da fonte."""
    if not dominio:
        return ""
    alvo = dominio.lower().replace("www.", "")
    for dominio_conhecido, orgao in ORGAO_POR_DOMINIO.items():
        if alvo == dominio_conhecido or alvo.endswith("." + dominio_conhecido):
            return orgao
    return ""


def classificar_orgao(texto: str) -> str:
    for orgao, padrao in _RE_ORGAOS.items():
        if padrao.search(texto or ""):
            return orgao
    return ""


def detectar(clipping: dict) -> dict:
    """Classifica um clipping como materia jornalistica ou propaganda publica."""
    texto = clipping.get("texto_limpo") or ""
    metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
    texto_ampliado = f"{texto} {metadados.get('veiculo', '')} {clipping.get('autor', '')}"

    resultado = {
        "classe": CLASSE_INDETERMINADA,
        "orgao": classificar_orgao(texto_ampliado),
        "tipo": "",
        "simbolos_publicos": bool(_RE_SIMBOLOS.search(texto_ampliado)),
        "marcas_publicas": [],
    }

    if _RE_INSTITUCIONAL.search(texto_ampliado):
        resultado["classe"] = CLASSE_PROPAGANDA
        resultado["tipo"] = "institucional" if not _RE_MIDIA_PAGA.search(texto_ampliado) else "publicidade"
    elif _RE_OFICIAL.search(texto_ampliado):
        resultado["classe"] = CLASSE_PROPAGANDA
        resultado["tipo"] = "oficial"
    elif _RE_LICITACAO.search(texto_ampliado):
        resultado["classe"] = CLASSE_PROPAGANDA
        resultado["tipo"] = "licitacao"
    elif _RE_MIDIA_PAGA.search(texto_ampliado):
        resultado["classe"] = CLASSE_PROPAGANDA
        resultado["tipo"] = "publicidade"

    if "utilidade publica" in _norm(texto_ampliado):
        resultado["classe"] = CLASSE_PROPAGANDA
        resultado["tipo"] = "utilidade_publica"

    if resultado["classe"] == CLASSE_INDETERMINADA:
        # materia jornalistica: agente citado como assunto, sem sinal de publicidade
        resultado["classe"] = CLASSE_JORNALISTICA

    marcas = []
    for orgao in ("camara", "prefeitura", "governo", "tribunal", "orgao_federal"):
        if resultado["orgao"] == orgao:
            marcas.append(orgao)
    resultado["marcas_publicas"] = marcas
    return resultado


def resumo(itens: list[dict]) -> dict:
    """Agrega o radar: volume, valor e distribuicao por orgao/tipo."""
    total = len(itens)
    propaganda = [
        i for i in itens
        if i.get("classe") in (CLASSE_PROPAGANDA, CLASSE_PUBLICACAO_OFICIAL)
    ]
    por_orgao: dict[str, int] = {}
    por_tipo: dict[str, int] = {}
    valor = 0.0
    for item in propaganda:
        orgao = item.get("orgao") or "nao_identificado"
        tipo = item.get("tipo") or "nao_identificado"
        por_orgao[orgao] = por_orgao.get(orgao, 0) + 1
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        valor += float(item.get("valor_estimado") or 0.0)
    simbolos = sum(1 for i in propaganda if i.get("simbolos_publicos"))
    return {
        "total_clippings": total,
        "total_propaganda": len(propaganda),
        "pct_propaganda": round(100.0 * len(propaganda) / total, 1) if total else 0.0,
        "por_orgao": por_orgao,
        "por_tipo": por_tipo,
        "valor_estimado": round(valor, 2),
        "com_simbolos_publicos": simbolos,
    }

