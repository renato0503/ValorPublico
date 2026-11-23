"""Extracao do "recorte" (trecho citado) e destaque de palavras-chave.

O clipping de radio/TV chega como transcricao integra; o que interessa ao
assessor e o trecho exato em que o agente aparece. Este modulo:

  - quebra o texto em frases;
  - escolhe as frases com maior densidade de termos monitorados;
  - devolve o trecho com offsets (para abrir em seeks no audio/video);
  - gera um HTML com <mark> nas palavras-chave (destaque no detalhe do clipping).

Sem dependencias externas e sem LLM: deterministico e auditavel.
"""

import html
import re
import unicodedata

MAX_TRECHO_CARACTERES = 420
MAX_FRASES = 3


def _norm(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


def _frases(texto: str) -> list[tuple[str, int]]:
    """Retorna [(frase, posicao_inicial_no_texto), ...]."""
    frases: list[tuple[str, int]] = []
    for match in re.finditer(r"[^.!?;\n]+[.!?;]?", texto or ""):
        bruto = match.group(0)
        inicio = match.start()
        limpo = bruto.strip()
        if limpo:
            frases.append((limpo, inicio))
    return frases


def _termos(termos: list[str] | None) -> list[str]:
    saida, vistos = [], set()
    for termo in termos or []:
        chave = _norm(termo)
        if len(chave) < 4 or chave in vistos:
            continue
        vistos.add(chave)
        saida.append(termo)
    return saida


def extrair_trecho(
    texto: str,
    termos: list[str] | None = None,
    max_frases: int = MAX_FRASES,
) -> dict:
    """Extrai o trecho mais relevante (frases com os termos monitorados).

    Retorna dict com:
        trecho          str  (texto do recorte)
        frases          list[str]
        termos_encontrados list[str]
        inicio/fim      offsets no texto original (quando aplicavel)
        cobertura_pct   % do texto que o recorte representa
    """
    vazio = {
        "trecho": "",
        "frases": [],
        "termos_encontrados": [],
        "inicio": 0,
        "fim": 0,
        "cobertura_pct": 0.0,
    }
    if not texto:
        return vazio

    lista = _termos(termos)
    frases = _frases(texto)
    if not frases:
        return vazio

    if not lista:
        # sem termos: usa as primeiras frases (resumo do inicio da materia)
        escolhidas = [(0, inicio, frase) for frase, inicio in frases[:max_frases]]
    else:
        pontuadas = []
        for frase, inicio in frases:
            fn = _norm(frase)
            peso = sum(1 for termo in lista if f" {_norm(termo)} " in f" {fn} ")
            if peso:
                pontuadas.append((peso, inicio, frase))
        if not pontuadas:
            escolhidas = [(0, inicio, frase) for frase, inicio in frases[:max_frases]]
        else:
            pontuadas.sort(key=lambda item: (-item[0], item[1]))
            escolhidas = sorted(pontuadas[:max_frases], key=lambda item: item[1])

    trecho_frases = [item[2] for item in escolhidas]
    inicio = min(item[1] for item in escolhidas)
    fim = max(item[1] + len(item[2]) for item in escolhidas)
    trecho = " ".join(trecho_frases)
    if len(trecho) > MAX_TRECHO_CARACTERES:
        trecho = trecho[:MAX_TRECHO_CARACTERES].rstrip() + "..."

    encontrados = [
        termo for termo in lista
        if f" {_norm(termo)} " in f" {_norm(trecho)} "
    ]
    return {
        "trecho": trecho,
        "frases": trecho_frases,
        "termos_encontrados": encontrados,
        "inicio": inicio,
        "fim": fim,
        "cobertura_pct": round(100.0 * min(len(trecho), len(texto)) / max(1, len(texto)), 1),
    }


def destacar(texto: str, termos: list[str] | None = None, tag: str = "mark") -> str:
    """Devolve HTML seguro com as palavras-chave destacadas (<mark>)."""
    if not texto:
        return ""
    escapado = html.escape(texto)
    for termo in _termos(termos):
        padrao = re.compile(r"(?<!\w)(" + re.escape(html.escape(termo)) + r")(?!\w)", re.IGNORECASE)
        escapado = padrao.sub(lambda m: f"<{tag}>{m.group(1)}</{tag}>", escapado)
    return escapado


def extrair_trecho_e_destaque(
    texto: str,
    termos: list[str] | None = None,
) -> tuple[dict, str]:
    """Atalho: devolve (dados do trecho, HTML destacado do trecho)."""
    dados = extrair_trecho(texto, termos)
    html_trecho = destacar(dados["trecho"], termos)
    return dados, html_trecho
