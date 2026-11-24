"""Classificacao de demandas do cidadao (plano 05 §9, plano 13 A4/V5, 14 §2.4).

Um "pedido" e um texto de comentario/DM/WhatsApp em que a pessoa pede alguma
coisa ao poder publico. O classificador e **por regra (regex + lexico)**, sem
modelo pago e sem dado sensivel: ele so olha o texto do cidadao.

LGPD (plano 05 §9): o classificador devolve TEMA, BAIRRO, URGENCIA e um
resumo. Nunca devolve nem guarda nome, foto ou perfil do comentarista.

Saida (uma demanda):
    {
      "e_demanda": bool,
      "tema": "saude" | "transporte" | ... | "outros",
      "bairro": "Jardim das Americas" | None,
      "urgencia": "alta" | "media" | "baixa",
      "acao_sugerida": "...",
      "motivo": "..."      # por que foi classificada assim (auditoria)
    }
"""

from __future__ import annotations

import re
import unicodedata

from cerra_nucleo.processing.bairros import detectar_bairro

# --------------------------------------------------------------------------
# Temas: o mesmo vocabulario usado em `processing/temas.py` dos apps, para
# a demanda cair na mesma classificacao do resto do painel.
# --------------------------------------------------------------------------
TEMAS: dict[str, tuple[str, ...]] = {
    "saude": (
        "upa", "hospital", "posto de saude", "sus", "medico", "enfermagem",
        "medicamento", "vacinacao", "saude mental", "psiquiatr",
    ),
    "educacao": (
        "escola", "creche", "professor", "aluno", "ensino", "universidade",
        "faculdade", "burocracia escolar",
    ),
    "transporte": (
        "onibus", "bus", "ponto de onibus", "transito", "transporte", "metro",
        "viagem", "rotula", "multa", "estacionamento", "motocicleta",
    ),
    "obras": (
        "asfalto", "buraco", "pavimentacao", "saneamento", "esgoto", "ponte",
        "calçada", "calcada", "rua quebrada", "drenagem", "obra",
    ),
    "seguranca": (
        "policia", "delegacia", "assalto", "roubo", "inseguranca",
        "iluminacao", "sinalizacao", "transito seguro", "vigilancia",
    ),
    "meio_ambiente": (
        "lixo", "coleta seletiva", "lixao", "desmatamento", "rio", "poluicao",
        "area verde", "praça", "praca",
    ),
    "habitacao": (
        "moradia", "mutirao", "casa propria", "aluguel", "levantamento",
        "bairro",
    ),
    "cultura": (
        "teatro", "museu", "festival", "cultura", "esporte", "quadra",
        "ginásio", "ginasio", "biblioteca",
    ),
    "servicos": (
        "documento", "cpf", "cadastro", "atendimento", "senha", "fila",
        "guia", "consulta",
    ),
}

# Palavras que indicam um pedido (o cidadao pede, reclama, cobra).
RE_PEDIDO = re.compile(
    r"\b(precis(?:o|am)|preciso|precisa|precisamos|gostaria|queria|quero|"
    r"quando|onde|como|por que|porque|nao (?:e|e'|foi|funciona|resolveu)|"
    r"faz(?:e|er|endo)?|instala|instale|arruma|arrume|conserta|conserte|"
    r"solve|resolva|reclamo|reclamacao|denuncia|denuncie|urgente|"
    r"demora|demorou|tardez|atrasad|nao atend|nao resolveram|prazo|"
    r"solicito|solicit|requer|encaminha|remete)\b",
    re.IGNORECASE,
)

# Sinais de urgencia (palavras cheias -> urgencia alta).
RE_URGENCIA_ALTA = re.compile(
    r"\b(urgente|emergencia|emergencia|perigo|risco|acidente|desabo|"
    r"alagament|infiltra|infec|doente|internad|criança|child|"
    r"vulnerable|imediat)\b",
    re.IGNORECASE,
)

RE_URGENCIA_MEDIA = re.compile(
    r"\b(demor\w+|atrasad\w*|nao atend\w*|reclam\w*|problema|"
    r"defeito|quebrad\w*|falta|parou|esper\w+|ja (?:faz|espero)|"
    r"ha (?:semanas|dias|meses)|prazo)\b",
    re.IGNORECASE,
)

RE_NAO_DEMANDA = re.compile(
    r"\b(parabens|parabéns|feliz|felicidade|obrigad|obrigado|"
    r"boa sorte|continue|parabens por)\b",
    re.IGNORECASE,
)

# Frases tipicas de divulgacao/piada que nao sao pedido.
RE_SPAM = re.compile(
    r"(https?://|clique aqui|compre|ganhe|oferta|promocao|cassino|"
    r"apostas|seguro|emprestimo|credi)",
    re.IGNORECASE,
)

_ACOES = {
    "saude": "Encaminhar para a Secretaria de Saude e cobrar prazo de atendimento.",
    "educacao": "Encaminhar para a Secretaria de Educacao (Secretaria de Estado / SME).",
    "transporte": "Encaminhar para a Secretaria de Mobilidade Urbana / operacao de onibus.",
    "obras": "Encaminhar para a Secretaria de Obras / 求 mistura de planejamento.",
    "seguranca": "Encaminhar para a Secretaria de Seguranca / Guarda Municipal.",
    "meio_ambiente": "Encaminhar para a Secretaria de Meio Ambiente / limpeza urbana.",
    "habitacao": "Encaminhar para a Secretaria de Habitacao / Regularizacao fundiaria.",
    "cultura": "Encaminhar para a Secretaria de Cultura / Esporte.",
    "servicos": "Encaminhar para a atendimento ao cidadao /protocolo geral.",
    "outros": "Classificar manualmente na fila da Base / Ouvidoria.",
}


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def classificar_demanda(texto: str, minimo_chars: int = 25) -> dict:
    """Classifica um texto de cidadao como demanda (ou nao).

    Devolve sempre o dicionario completo (mesmo quando `e_demanda` e False),
    para o chamador poder exibir o motivo na fila.
    """
    bruto = (texto or "").strip()
    limpo = _sem_acento(bruto)
    saida: dict = {
        "e_demanda": False,
        "tema": "outros",
        "bairro": None,
        "urgencia": "baixa",
        "acao_sugerida": "",
        "motivo": "",
    }

    if len(bruto) < minimo_chars:
        saida["motivo"] = "Texto curto demais para classificar como pedido."
        return saida

    if RE_SPAM.search(bruto):
        saida["motivo"] = "Parece divulgacao ou link comercial, nao e pedido."
        return saida

    if RE_NAO_DEMANDA.search(bruto) and not RE_PEDIDO.search(bruto):
        saida["motivo"] = "Texto de elogio ou agradecimento, sem pedido."
        return saida

    if not RE_PEDIDO.search(limpo):
        saida["motivo"] = "Nao encontrei indicacao de pedido no texto."
        return saida

    # Tema: o que mais aparece no texto.
    tema = "outros"
    melhor = 0
    for nome, termos in TEMAS.items():
        pontos = sum(1 for termo in termos if termo in limpo)
        if pontos > melhor:
            melhor = pontos
            tema = nome
    saida["tema"] = tema

    bairro = detectar_bairro(bruto)
    saida["bairro"] = bairro

    if RE_URGENCIA_ALTA.search(limpo):
        saida["urgencia"] = "alta"
    elif RE_URGENCIA_MEDIA.search(limpo):
        saida["urgencia"] = "media"

    saida["e_demanda"] = True
    saida["acao_sugerida"] = _ACOES.get(tema, _ACOES["outros"])
    saida["motivo"] = (
        f"Texto com indicacao de pedido; tema '{tema}'"
        + (f"; bairro {bairro}" if bairro else "; sem bairro identificado")
        + f"; urgencia {saida['urgencia']}."
    )
    return saida


def temais_de_demanda(textos: list[str]) -> dict:
    """Agrega uma lista de textos em contagens por tema/bairro/urgencia.

    Usado pelo agregado `demandas` (so numeros; sem nome do cidadao).
    """
    por_tema: dict[str, int] = {}
    por_bairro: dict[str, int] = {}
    por_urgencia: dict[str, int] = {}
    total = 0
    for texto in textos:
        r = classificar_demanda(texto)
        if not r["e_demanda"]:
            continue
        total += 1
        por_tema[r["tema"]] = por_tema.get(r["tema"], 0) + 1
        por_urgencia[r["urgencia"]] = por_urgencia.get(r["urgencia"], 0) + 1
        if r["bairro"]:
            por_bairro[r["bairro"]] = por_bairro.get(r["bairro"], 0) + 1
    return {
        "total": total,
        "por_tema": dict(sorted(por_tema.items(), key=lambda kv: -kv[1])),
        "por_bairro": dict(sorted(por_bairro.items(), key=lambda kv: -kv[1])),
        "por_urgencia": por_urgencia,
    }
