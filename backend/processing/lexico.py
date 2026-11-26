"""Vocabulário das análises lexicais (plano 22): palavras sem assunto e temas.

Fonte única: ``frontend/assets/dados/lexico.json`` (o app usa o mesmo arquivo
para filtrar o que aparece nos gráficos e dar nome aos grupos).
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "dados" / "lexico.json"


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return base.lower().strip()


@lru_cache(maxsize=1)
def _dados() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sem_assunto": [], "temas": []}


@lru_cache(maxsize=1)
def sem_assunto() -> frozenset[str]:
    return frozenset(_norm(p) for p in _dados().get("sem_assunto", []))


def relevante(palavra: str) -> bool:
    p = _norm(palavra)
    return len(p) >= 3 and not p.isdigit() and p not in sem_assunto()


def _casa(palavra: str, radical: str) -> bool:
    p, r = _norm(palavra), _norm(radical)
    if not p or not r:
        return False
    if len(r) <= 3:
        return p == r
    return p.startswith(r)


def tema(palavras: list[str]) -> dict | None:
    """Tema que melhor descreve uma lista de palavras (as primeiras pesam mais)."""
    melhor, nota_melhor = None, 0.0
    for t in _dados().get("temas", []):
        nota = 0.0
        for i, palavra in enumerate(palavras[:12]):
            if any(_casa(palavra, r) for r in t.get("radicais", [])):
                nota += 1.0 / (1 + i * 0.35)
        if nota > nota_melhor:
            melhor, nota_melhor = t, nota
    if not melhor or nota_melhor < 0.6:
        return None
    return {"id": melhor["id"], "nome": melhor["nome"], "descricao": melhor["descricao"]}


def peso(pct: float) -> str:
    if pct >= 25:
        return "é o assunto dominante do período"
    if pct >= 8:
        return "é um assunto relevante do período"
    if pct >= 2:
        return "é um assunto secundário"
    return "é uma pauta pontual, de poucas notícias"


_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\-]*")


def legiveis(palavras: list[str], textos: list[str]) -> dict[str, str]:
    """Forma usada nas manchetes para cada palavra reduzida da análise.

    A análise trabalha sem acento e com plural cortado ("inscricoe", "servidore");
    para mostrar, usa a grafia mais comum nas manchetes ("inscrições", "servidores").
    """
    alvo = {_norm(p): p for p in palavras}
    contagem: dict[str, dict[str, int]] = {k: {} for k in alvo}
    for texto in textos:
        for original in _PALAVRA.findall(texto or ""):
            n = _norm(original)
            for chave in alvo:
                if n == chave or (len(chave) >= 4 and n.startswith(chave) and len(n) - len(chave) <= 2):
                    contagem[chave][original] = contagem[chave].get(original, 0) + 1
    saida = {}
    for chave, original in alvo.items():
        opcoes = contagem.get(chave) or {}
        if not opcoes:
            saida[original] = original
            continue
        # junta as grafias pela forma minúscula e escolhe a palavra mais comum
        por_minuscula: dict[str, dict[str, int]] = {}
        for forma, n in opcoes.items():
            por_minuscula.setdefault(forma.lower(), {})[forma] = n
        minuscula, variantes = max(por_minuscula.items(), key=lambda kv: sum(kv[1].values()))
        total = sum(variantes.values())
        # maiúscula só quando é nome próprio/sigla (quase sempre escrito assim)
        if variantes.get(minuscula, 0) >= 0.3 * total:
            saida[original] = minuscula
        else:
            saida[original] = max(variantes.items(), key=lambda kv: kv[1])[0]
    return saida


def sem_veiculo(titulo: str) -> str:
    """Manchete sem o " - Veículo" que o agregador cola no fim."""
    partes = (titulo or "").rsplit(" - ", 1)
    return partes[0].strip() if len(partes) == 2 and len(partes[1]) <= 60 else (titulo or "").strip()


def explicar(
    palavras: list[str],
    pct: float,
    exemplos: list[str] | None = None,
    textos: list[str] | None = None,
) -> dict:
    """Nome e explicação em linguagem simples de um grupo (cluster)."""
    uteis = [p for p in palavras if relevante(p)]
    if textos:
        mapa = legiveis(uteis[:12], textos)
        uteis = [mapa.get(p, p) for p in uteis]
    t = tema(uteis)
    chave = ", ".join(uteis[:4]) if uteis else "palavras variadas"
    pct_txt = f"{pct:.1f}".replace(".", ",")
    temas_misturados = {x["id"] for x in (tema([p]) for p in uteis[:10]) if x}
    if pct >= 30 and len(temas_misturados) >= 3:
        # grupo "resto": junta o que nao formou assunto proprio
        nome = f"Noticiário geral: {', '.join(uteis[:2])}" if uteis else "Noticiário geral"
        texto = (
            "É o grupo onde caem as notícias do dia a dia que não formam um assunto próprio: "
            f"mistura vários temas, e as palavras mais marcantes são {chave}. Reúne {pct_txt}% dos trechos. "
            "Para a leitura, os grupos menores ao lado dizem mais sobre as pautas específicas."
        )
        if exemplos:
            texto += f" Exemplo: “{exemplos[0]}”."
        return {"tema": "geral", "nome": nome, "explicacao": texto, "palavras_relevantes": uteis[:12]}
    if t:
        nome = f"{t['nome']}: {', '.join(uteis[:2])}" if uteis else t["nome"]
        texto = (
            f"Notícias sobre {t['descricao']}. As palavras que marcam o grupo são {chave}. "
            f"Reúne {pct_txt}% dos trechos e {peso(pct)}."
        )
    elif uteis:
        nome = f"Assunto: {', '.join(uteis[:2])}"
        texto = (
            f"Grupo sem um tema único; as palavras que o marcam são {chave}. "
            f"Reúne {pct_txt}% dos trechos e {peso(pct)}."
        )
    else:
        nome = "Mensagens genéricas"
        texto = (
            "Grupo formado por frases genéricas (cumprimentos, apoio, convites), sem um assunto de governo. "
            f"Reúne {pct_txt}% dos trechos e {peso(pct)}; pode ser ignorado na leitura."
        )
    if exemplos:
        texto += f" Exemplo: “{exemplos[0]}”."
    return {"tema": t["id"] if t else "", "nome": nome, "explicacao": texto, "palavras_relevantes": uteis[:12]}


def exemplos_por_palavras(palavras: list[str], textos: list[str], n: int = 3) -> list[str]:
    """As manchetes que mais usam as palavras típicas do grupo."""
    alvo = [_norm(p) for p in palavras[:8] if relevante(p)]
    if not alvo:
        return []
    pontuados = []
    vistos = set()
    for bruto in textos:
        texto = sem_veiculo(bruto)
        t = _norm(texto)
        if not t or t in vistos:
            continue
        nota = sum(1 for p in alvo if re.search(rf"(?<![a-z0-9]){re.escape(p)}", t))
        if nota:
            pontuados.append((nota, len(texto), texto))
            vistos.add(t)
    pontuados.sort(key=lambda x: (-x[0], x[1]))
    return [texto for _, _, texto in pontuados[:n]]
