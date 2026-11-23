"""Motor de compliance eleitoral (Lei 9.504/1997 - Lei das Eleicoes).

Regras implementadas (texto oficial em `pesquisa/05_FONTES.md` / fontes/lei9504):

  Art. 39     Ato de propaganda em recinto aberto/fechado nao depende de licenca
              policial, mas exige comunicacao a autoridade policial com no minimo
              24h de antecedencia.
  Art. 39-A   No dia da eleicao e permitida apenas manifestacao individual e
              silenciosa (bandeiras, broches, distintivos, adesivos).
  Art. 40     Usar simbolo, frase ou imagem de orgao de governo, empresa publica
              ou economia mista na propaganda eleitoral e CRIME (detencao de 6
              meses a 1 ano + multa de 10 a 20 mil UFIR).
  Art. 45     A partir de 1 de julho, emissoras nao podem veicular pesquisa
              identificavel, trucagem que degrade candidato, propaganda politica
              no noticiario, tratamento privilegiado ou alusoes em programas.
  Art. 49     No segundo turno, o horario eleitoral gratuito e dividido em dois
              blocos diarios de 10 minutos (radio 7h e 12h; TV 13h e 20h30).
  Art. 53     Vedados cortes instantaneos e censura previa; vedada propaganda que
              degrade ou ridicularize candidato (perda do horario no dia seguinte).
  Art. 55     Inobservanca das vedaes -> perda de tempo igual ao dobro do ilicito.
  Art. 56     A Justica Eleitoral pode suspender por 24h a emissora que descumprir
              a lei electoral.
  Art. 57-A   Propaganda eleitoral na internet e permitida a partir de 15 de
              agosto.
  Impulsionamento (art. 26) conteudo priorizado pago e gasto eleitoral, sujeito
  a prestacao de contas.

O motor e 100% deterministico e devolve sempre a base legal, para que o alerta
seja auditavel.
"""

import re
import unicodedata
from datetime import date, datetime

NIVEL_ALERTA = "alerta"
NIVEL_ATENCAO = "atencao"
NIVEL_INFO = "info"

# Calendario eleitoral BR (configuravel por settings).
# 2026 - eleicao geral: 1o turno 04/10/2026, 2o turno 25/10/2026.
# 2024 - eleicao municipal: 1o turno 06/10/2024, 2o turno 27/10/2024.
CALENDARIO_ELEITORAL = {
    "2026": {"1o_turno": date(2026, 10, 4), "2o_turno": date(2026, 10, 25)},
    "2024": {"1o_turno": date(2024, 10, 6), "2o_turno": date(2024, 10, 27)},
}

# Inicio do horario eleitoral gratuito (art. 49) no 2o turno: sexta seguinte ao 1o turno
INICIO_PROPAGANDA_ELEITORAL = date(2026, 7, 15)
INICIO_PROPAGANDA_INTERNET = date(2026, 8, 15)

# Sinais de ato de propaganda em recinto (art. 39)
_RE_ATO = re.compile(
    r"\b(com[ií]cios?|comicios?|eventos?|carro de som|trio el[eé]ctrico|trio eletrico|"
    r"palcos?|desfiles?|marchas?|caravanas?|palanques?|shows?|ensaios?|concentra[cç][õo]es?|"
    r"reuni[õo]es? p[úu]blicas?|reunioes? publicas?|assembleias?|plebiscitos?|referendums?)\b",
    re.IGNORECASE,
)
# Materiais usados em ato de propaganda (art. 39-A: vedados no dia da eleicao)
_RE_MATERIAIS = re.compile(
    r"\b(bandeiras?|broches?|distintivos?|adesivos?|santinhos?|panfletos?|carro de som|"
    r"alto-falantes?|alto falantes?|com[ií]cios?|comicios?|shows?|caravanas?)\b",
    re.IGNORECASE,
)
# Simbolos publicos (art. 40)
_RE_SIMBOLOS = re.compile(
    r"\b(bras[aã]o|bandeira do (munic[ií]pio|estado)|bras[aã]o municipal|"
    r"escudo (do|de)|logotipo (do|de) (prefeitura|governo|c[âa]mara)|"
    r"prefeitura de \w+ ap(?:oó|o)s|governo do estado ap(?:oó|o)s|"
    r"maquina do estado|carro oficial|palacio do governo)\b",
    re.IGNORECASE,
)
# Pesquisa eleitoral (art. 45)
_RE_PESQUISA = re.compile(
    r"\b(pesquisa (electoral|de inten[cç][aã]o)|levantamento|"
    r"apontou \d+|[\d]{1,2}[.,]\d\s?% (dos|das) (eleitores|intervistados))\b",
    re.IGNORECASE,
)
# Impulsionamento / midia paga (art. 26 - gasto eleitoral)
_RE_IMPULSIONAMENTO = re.compile(
    r"\b(impulsionamento|impulsionado|boost|patrocinad[oa]|an[úu]ncio pago|"
    r"publicidade paga|midia paga)\b",
    re.IGNORECASE,
)
# Debate / programa eleitoral
_RE_DEBATE = re.compile(r"\b(debate|hor[aá]rio eleitoral|programa eleitoral|com appearances)\b", re.IGNORECASE)

_RE_SIMBOLOS_PUBLICOS = re.compile(
    r"\b(bras[aã]o|escudo municipal|bandeira do munic[ií]pio|"
    r"logotipo da prefeitura|logotipo do governo|pal[aá]cio do governo|"
    r"maquina do estado|carro oficial)\b",
    re.IGNORECASE,
)


def _norm(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


def _data_de(clipping: dict) -> date | None:
    valor = clipping.get("data_publicacao")
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and valor:
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(valor[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _texto(clipping: dict) -> str:
    return clipping.get("texto_limpo") or ""


def _plataforma(clipping: dict) -> str:
    return (clipping.get("plataforma") or "").lower()


def _datas_eleitorais() -> list[tuple[date, str]]:
    datas: list[tuple[date, str]] = []
    for ano, turnos in CALENDARIO_ELEITORAL.items():
        for turno, dia in turnos.items():
            datas.append((dia, f"{ano} {turno.replace('_', ' ')}"))
    return sorted(datas)


def dias_para_eleicao(data_ref: date | None = None) -> tuple[int | None, str | None]:
    """Retorna (dias ate a proxima eleicao, rotulo). Negativo = eleicao passou."""
    if data_ref is None:
        data_ref = date.today()
    elif isinstance(data_ref, datetime):
        data_ref = data_ref.date()
    futuro: tuple[int, str] | None = None
    passado: tuple[int, str] | None = None
    for dia, rotulo in _datas_eleitorais():
        delta = (dia - data_ref).days
        if delta >= 0:
            if futuro is None or delta < futuro[0]:
                futuro = (delta, rotulo)
        elif passado is None or delta > passado[0]:
            passado = (delta, rotulo)
    melhor = futuro or passado
    return melhor if melhor else (None, None)


def analisar(
    clipping: dict,
    calendario: dict | None = None,
    inicio_propaganda: date | None = None,
    inicio_internet: date | None = None,
) -> list[dict]:
    """Analisa um clipping e devolve a lista de apontamentos de compliance.

    Cada apontamento: {artigo, regra, nivel, motivo, data_referencia}
    """
    texto = _texto(clipping)
    if not texto:
        return []
    plataforma = _plataforma(clipping)
    data = _data_de(clipping)
    achados: list[dict] = []

    def add(artigo: str, regra: str, nivel: str, motivo: str) -> None:
        achados.append({
            "artigo": artigo,
            "regra": regra,
            "nivel": nivel,
            "motivo": motivo,
            "data_referencia": data.isoformat() if data else None,
        })

    # --- Art. 40: uso de simbolo de orgao publico em propaganda eleitoral ---
    if _RE_SIMBOLOS.search(texto) or _RE_SIMBOLOS_PUBLICOS.search(texto):
        add(
            "Art. 40",
            "Uso de simbolo, frase ou imagem de orgao de governo em propaganda eleitoral",
            NIVEL_ALERTA,
            "Texto referencia simbolo/identidade de orgao publico em contexto de propaganda",
        )

    # --- Art. 39 / 39-A: atos de propaganda e MATERIAL no dia da eleicao ---
    dias, rotulo = dias_para_eleicao(data)
    eh_dia_eleicao = bool(dias is not None and dias == 0)
    if eh_dia_eleicao and _RE_MATERIAIS.search(texto):
        add(
            "Art. 39-A",
            "No dia da eleicao somente e permitida manifestacao individual e silenciosa",
            NIVEL_ALERTA,
            f"Mencoes a material/ato de propaganda no dia da eleicao ({rotulo})",
        )
    elif _RE_ATO.search(texto) and dias is not None and 0 <= dias <= 7:
        add(
            "Art. 39",
            "Ato de propaganda em recinto aberto/fechado exige comunicacao com 24h de antecedencia",
            NIVEL_ATENCAO,
            f"Ato de propaganda proximo da eleicao ({rotulo}, faltam {dias} dias)",
        )

    # --- Art. 45: emissoras (radio/TV) e pesquisa identificavel ---
    if plataforma in ("tv", "radio") and _RE_PESQUISA.search(texto):
        add(
            "Art. 45",
            "Vedado a emissoras veicular pesquisa com-netos identificaveis ou degradar candidato",
            NIVEL_ATENCAO,
            "Pesquisa electoral ou percentual apurado em material de radio/TV",
        )

    # --- Art. 53: degradação/ridicularização ---
    if re.search(
        r"\b(ridiculariz\w+|degrad\w+|zomb\w+|vazou a tread|calúnia|acusou de)\b",
        texto,
        re.IGNORECASE,
    ):
        add(
            "Art. 53",
            "Vedada propaganda que degrade ou ridicularize candidato",
            NIVEL_ATENCAO,
            "Aparecem termos de degradação/ridicularização na materia",
        )

    # --- Art. 57-A: propaganda na internet antes de 15/08 ---
    limiar = inicio_internet or INICIO_PROPAGANDA_INTERNET
    if data and plataforma in ("twitter", "instagram", "facebook", "youtube", "telegram", "web"):
        if data < limiar and _RE_ATO.search(texto):
            add(
                "Art. 57-A",
                "Propaganda eleitoral na internet permitida apenas a partir de 15 de agosto",
                NIVEL_ALERTA,
                f"Conteudo de propaganda em internet publicado em {data.isoformat()} (antes de {limiar.isoformat()})",
            )

    # --- Impulsionamento: gasto eleitoral sujeito a prestacao de contas ---
    if _RE_IMPULSIONAMENTO.search(texto):
        add(
            "Art. 26",
            "Impulsionamento e despesa de natureza electoral, sujeita a prestacao de contas",
            NIVEL_INFO,
            "Mencao a midia paga/impulsionamento",
        )

    # --- Art. 49: grade do horario eleitoral gratuito no 2o turno ---
    if _RE_DEBATE.search(texto) and data:
        for dia, rotulo in _datas_eleitorais():
            if "2o turno" in rotulo and abs((data - dia).days) <= 3:
                add(
                    "Art. 49",
                    "No 2o turno: radio 7h e 12h, TV 13h e 20h30 (blocos de 10 minutos)",
                    NIVEL_INFO,
                    f"Debate/horario eleitoral proximo do {rotulo} ({dia.isoformat()})",
                )
                break

    return achados


def resumo(achados: list[dict]) -> dict:
    """Resume os apontamentos para o painel."""
    if not achados:
        return {"total": 0, "alerta": 0, "atencao": 0, "info": 0, "artigos": []}
    niveis = {"alerta": 0, "atencao": 0, "info": 0}
    artigos = []
    for achado in achados:
        niveis[achado["nivel"]] = niveis.get(achado["nivel"], 0) + 1
        if achado["artigo"] not in artigos:
            artigos.append(achado["artigo"])
    return {
        "total": len(achados),
        "alerta": niveis["alerta"],
        "atencao": niveis["atencao"],
        "info": niveis["info"],
        "artigos": artigos,
    }


def nivel_maximo(achados: list[dict]) -> str:
    if any(a.get("nivel") == NIVEL_ALERTA for a in achados):
        return NIVEL_ALERTA
    if any(a.get("nivel") == NIVEL_ATENCAO for a in achados):
        return NIVEL_ATENCAO
    if achados:
        return NIVEL_INFO
    return ""
