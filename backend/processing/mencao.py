"""Classificacao da mencao a um agente/marca (padrao "DSM").

Segue o padrao de mercado usado por agencies como Dinamica Clipping/DSM: a
mencao e classificada como DIRECT, INDIRECT or INDETERMINATE, e o sujeito e
classificado as PROTAGONIST, SPOKESPERSON or merely CITED.

The classification is rule-based (no LLM): fast, free and auditable. Each rule
is documented so that the result can be explained in the audit trail.

Outputs (dict):
    tipo         "direta" | "indireta" | "indeterminada"
    papel        "protagonista" | "porta-voz" | "citada"
    porta_vozes  list[str]  (names detected with a cargo/predicate)
    occurrences  int
    confianca    float (0..1)
    motivos      list[str]  (why the classification was made - audit trail)
"""

import re
import unicodedata

MencaoDireta = "direta"
MencaoIndireta = "indireta"
MencaoIndeterminada = "indeterminada"

PapelProtagonista = "protagonista"
PapelPortaVoz = "porta-voz"
PapelCitada = "citada"

# Signals that the text is actually citing someone (direct quote / attribution)
_SINAIS_CITACAO = (
    "disse", "afirmou", "declarou", "defendeu", "apontou", "garantiu", "explicou",
    "contou", "relatou", "ressaltou", "destacou", "acrescentou", "completou",
    "segundo", "para ele", "para ela", "citou", "falou", "declara", "afirma",
    "durante a sessao", "em seu pronunciamento",
)

# Signals that the text is generic/aggregated (no attribution to the subject)
_SINAIS_GENERICOS = (
    "segundo dados", "de acordo com dados", "levantamento", "pesquisa aponta",
    "boletim", "agregou", "em resumo", "ao longo do dia", "noticiou",
    "publicou", "divulgou", "registrou", "aparece entre", "lista",
)

# Cargo/predicate that identifies a spokesperson
_CARGOS = (
    "vereador", "vereadora", "presidente da camara", "vice-presidente", "secretario",
    "secretaria", "deputado", "deputada", "senador", "prefeito", "prefeita",
    "governador", "governadora", "procurador", "delegado", "capitao", "coronel",
    "presidente", "diretor", "coordenador", "líder", "lider",
)

_RE_CARGOS = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _CARGOS) + r")\b", re.IGNORECASE
)
_RE_SINAIS_CITACAO = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _SINAIS_CITACAO) + r")\b", re.IGNORECASE
)
_RE_SINAIS_GENERICOS = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _SINAIS_GENERICOS) + r")\b", re.IGNORECASE
)
_RE_CIFRA = re.compile(r"\d+[\.,]?\d*\s*%")
_RE_NOME_PROPRIO = re.compile(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}){0,2})\b")

# nomes institucionais que nao sao pessoas (evita falso porta-voz)
_NAO_PESSOAS = {
    "camara", "camara municipal", "camara de vereadores", "prefeitura", "prefeitura municipal",
    "governo", "governo do estado", "estado", "municipio", "universidade", "secretaria",
    "tribunal", "poder judiciario", "ministerio publico", "defensoria publica",
    "poder legislativo", "poder executivo", "assembleia", "senado", "conselho",
}


def _norm(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?;:\n])\s+", texto or "") if f.strip()]


def _termos_agente(agente: dict | None, extra: list[str] | None = None) -> list[str]:
    """Monta a lista de termos que identificam o agente/marca monitorado."""
    termos: list[str] = []
    if agente:
        for chave in ("termos_de_busca", "termos", "nomes"):
            valor = agente.get(chave)
            if isinstance(valor, (list, tuple)):
                termos.extend(str(v) for v in valor if str(v).strip())
        for chave in ("nome_urna", "nome", "titulo"):
            valor = agente.get(chave)
            if valor:
                termos.append(str(valor))
    if extra:
        termos.extend(str(t) for t in extra if str(t).strip())
    vistos, unicos = set(), []
    for t in termos:
        chave = _norm(t)
        if len(chave) < 4 or chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(t)
    return unicos


def _contem(frase_norm: str, termo_norm: str) -> bool:
    return f" {termo_norm} " in f" {frase_norm} "


def classificar_mencao(
    texto: str,
    termos: list[str] | None = None,
    agente: dict | None = None,
) -> dict:
    """Classifica a mencao a um agente/marca em um texto.

    Regras (em ordem de precedencia):
      1. O termo nao aparece -> "indeterminada" (sem mencao relevante).
      2. Termo em frase com sinal de citacao ("disse", "segundo"...) ou no
         titulo/primeira frase -> "direta".
      3. Termo aparece so em contexto generico/agregado -> "indeterminada".
      4. Caso contrario -> "indireta".
    """
    resultado = {
        "tipo": MencaoIndeterminada,
        "papel": PapelCitada,
        "porta_vozes": [],
        "occurrences": 0,
        "confianca": 0.0,
        "motivos": [],
    }
    if not texto:
        resultado["motivos"].append("sem texto")
        return resultado

    lista_termos = _termos_agente(agente, termos)
    if not lista_termos:
        resultado["motivos"].append("sem termos de busca definidos")
        return resultado

    frases = _frases(texto)
    if not frases:
        return resultado
    frases_norm = [_norm(f) for f in frases]
    termos_norm = [(t, _norm(t)) for t in lista_termos]
    termos_encontrados = [t for t, tn in termos_norm if any(_contem(fn, tn) for fn in frases_norm)]
    resultado["occurrences"] = sum(
        1 for fn in frases_norm for _, tn in termos_norm if _contem(fn, tn)
    )

    if not termos_encontrados:
        resultado["motivos"].append("termo monitorado ausente do texto")
        return resultado

    # frase que efetivamente cita
    frases_citacao = []
    for frase, fn in zip(frases, frases_norm):
        if not any(_contem(fn, tn) for _, tn in termos_norm):
            continue
        if _RE_SINAIS_CITACAO.search(frase):
            frases_citacao.append(frase)
    primeira = frases_norm[0]
    titulo = primeira
    mencao_no_titulo = any(_contem(titulo, tn) for _, tn in termos_norm)

    if frases_citacao or mencao_no_titulo:
        resultado["tipo"] = MencaoDireta
        resultado["confianca"] = 0.85 if frases_citacao else 0.7
        resultado["motivos"].append(
            "atribuicao explicita do agente" if frases_citacao else "agente citado no titulo"
        )
    else:
        frases_genericas = [
            frase for frase, fn in zip(frases, frases_norm)
            if _RE_SINAIS_GENERICOS.search(frase)
            and any(_contem(fn, tn) for _, tn in termos_norm)
        ]
        if frases_genericas and len(frases_genericas) >= resultado["occurrences"]:
            resultado["tipo"] = MencaoIndeterminada
            resultado["confianca"] = 0.55
            resultado["motivos"].append("mencao em contexto generico/agregado")
        else:
            resultado["tipo"] = MencaoIndireta
            resultado["confianca"] = 0.6
            resultado["motivos"].append("agente citado sem atribuicao direta")

    # papel do agente
    total_frases = len(frases)
    if resultado["tipo"] == MencaoIndireta:
        resultado["papel"] = PapelCitada
    elif mencao_no_titulo or resultado["occurrences"] >= max(2, total_frases * 0.4):
        resultado["papel"] = PapelProtagonista
        resultado["motivos"].append("agente no titulo ou recorrente no texto")
    else:
        resultado["papel"] = PapelCitada

    # porta-vozes (pessoa citada com cargo)
    porta_vozes = []
    for frase in frases:
        if not _RE_CARGOS.search(frase):
            continue
        for nome in _RE_NOME_PROPRIO.findall(frase):
            if _norm(nome) in _NAO_PESSOAS:
                continue
            if any(_norm(nome) == _norm(pv) for pv in porta_vozes):
                continue
            porta_vozes.append(nome)
    if porta_vozes:
        resultado["porta_vozes"] = porta_vozes[:5]
        if resultado["papel"] == PapelCitada:
            resultado["papel"] = PapelPortaVoz
            resultado["motivos"].append("ha pessoa citada com cargo")
    return resultado


def aplicar_mencao(clipping: dict, agente: dict | None = None) -> dict:
    """Classifica a mencao de um clipping e devolve o dicionario de campos."""
    termos = (clipping.get("metadados") or {}).get("termos_de_busca") if isinstance(
        clipping.get("metadados"), dict
    ) else None
    return classificar_mencao(
        clipping.get("texto_limpo", ""),
        termos=list(termos) if isinstance(termos, (list, tuple)) else None,
        agente=agente,
    )


def resumir_mencoes(itens: list[dict]) -> dict:
    """Agrega classificacoes de mencao em indicadores (share of voice por tipo)."""
    total = len(itens)
    if not total:
        return {"total": 0, "direta": 0, "indireta": 0, "indeterminada": 0, "pct_direta": 0.0}
    contagem = {"direta": 0, "indireta": 0, "indeterminada": 0}
    for item in itens:
        tipo = (item or {}).get("tipo_mencao") or (item or {}).get("mencao", {}).get("tipo")
        if tipo in contagem:
            contagem[tipo] += 1
    return {
        "total": total,
        "direta": contagem["direta"],
        "indireta": contagem["indireta"],
        "indeterminada": contagem["indeterminada"],
        "pct_direta": round(100.0 * contagem["direta"] / total, 1),
        "pct_indireta": round(100.0 * contagem["indireta"] / total, 1),
        "pct_indeterminada": round(100.0 * contagem["indeterminada"] / total, 1),
    }
