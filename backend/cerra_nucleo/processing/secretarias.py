"""Classifica uma noticia em uma ou mais secretarias do Governo de Mato Grosso.

Regra **multi-label** com pesos e motivo (auditoria), no mesmo spirit do
`mencao.py` (plano 14): a saida sempre explica *por que* a pasta foi atribuida.

Pesos:
  - nome completo da secretaria no texto ............ +4
  - sigla da secretaria (palavra inteira, maiuscula) .. +3
  - alias (ex.: SERMAT) ............................. +3
  - termo tematico (saude, obra, ...) .............. +1 cada

Limiar: entra no rotulo se pontuar >= 2 OU casar nome/sigla. Uma materia sobre
saude e obras entra nas duas (e na "geral" quando nenhuma casa tem forca).

Entrada/saida (funcoes puras, faceis de testar):

    classificar(texto, secretarias) -> {
        "secretarias": ["saude", "obras"],
        "rotulos": ["SES", "SINFRA"],
        "alvos": ["governo-mt", "governador"],
        "confianca": 0.78,
        "motivo": {"saude": ["saúde (tema)", "SES (sigla)"], ...},
        "geral": False,
    }
"""

from __future__ import annotations

import re
import unicodedata

PESO_NOME = 4
PESO_TERMO = 3
PESO_SIGLA = 3
PESO_ALIAS = 3
PESO_TEMA = 1
LIMIAR_TEMA = 2

GERAL = "geral-governo"


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(texto)).strip()


def carregar_secretarias(caminho_json) -> list[dict]:
    """Le o seed do Governo de MT e devolve a lista de secretarias."""
    import json
    from pathlib import Path

    dados = json.loads(Path(caminho_json).read_text(encoding="utf-8"))
    return dados.get("secretarias", [])


def classificar(
    texto: str,
    secretarias: list[dict],
    *,
    governador: dict | None = None,
    interino: dict | None = None,
    termos_gerais: list[str] | None = None,
) -> dict:
    """Classifica o texto nas secretarias (multi-label) e nos alvos.

    `secretarias`: itens com `slug`, `sigla`, `nome`, `termos`, `temas`,
    opcionalmente `alias`.
    """
    limpo = _normalizar(texto)
    original = texto or ""
    pontos: dict[str, dict] = {}
    casou_nome_ou_sigla: set[str] = set()

    def registrar(slug: str, motivo: str, peso: int, nome_ou_sigla: bool) -> None:
        item = pontos.setdefault(slug, {"pontos": 0, "motivos": []})
        item["pontos"] += peso
        if motivo not in item["motivos"]:
            item["motivos"].append(motivo)
        if nome_ou_sigla:
            casou_nome_ou_sigla.add(slug)

    for secretaria in secretarias:
        slug = secretaria.get("slug")
        if not slug:
            continue
        sigla = (secretaria.get("sigla") or "").strip()
        nome = _normalizar(secretaria.get("nome") or "")
        alias = [_normalizar(a) for a in (secretaria.get("alias") or [])]

        # nome completo (sem a palavra "Secretaria de Estado de", que e generica)
        nome_sem_generico = re.sub(r"^secretaria de estado d[eoa]s?\s*", "", nome).strip()
        if nome and nome in limpo:
            registrar(slug, f"nome oficial ({nome})", PESO_NOME, True)
        elif nome_sem_generico and len(nome_sem_generico) > 6 and nome_sem_generico in limpo:
            registrar(slug, f"nome da pasta ({nome_sem_generico})", PESO_NOME, True)

        # sigla: precisa ser palavra inteira E maiuscula no texto original
        if sigla and len(sigla) >= 2:
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(sigla)}(?![A-Za-z0-9])", original):
                registrar(slug, f"sigla ({sigla})", PESO_SIGLA, True)
            elif sigla.isupper() and re.search(rf"(?<![a-z0-9]){re.escape(sigla.lower())}(?![a-z0-9])", limpo):
                registrar(slug, f"sigla em minusculo ({sigla})", PESO_SIGLA, True)
        for item_alias in alias:
            if item_alias and re.search(
                rf"(?<![A-Za-z0-9]){re.escape(item_alias)}(?![A-Za-z0-9])", original
            ):
                registrar(slug, f"alias ({item_alias.upper()})", PESO_ALIAS, True)

        # termos oficiais da pasta (sinal forte): "policia civil", "hospital central",
        # "radio paiaguas", "defensoria publica"...
        for termo in secretaria.get("termos") or []:
            termo_norm = _normalizar(termo)
            if len(termo_norm) < 5:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(termo_norm)}(?![a-z0-9])", limpo):
                registrar(slug, f"termo oficial ({termo})", PESO_TERMO, True)

        # temas (sinal fraco): precisa de 2 ou mais, ou o contexto do governo
        for tema in secretaria.get("temas") or []:
            tema_norm = _normalizar(tema)
            if len(tema_norm) < 4:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(tema_norm)}(?![a-z0-9])", limpo):
                registrar(slug, f"tema ({tema})", PESO_TEMA, False)

    rotulos: list[str] = []
    motivo: dict[str, list[str]] = {}
    total_pontos = 0
    for slug, item in pontos.items():
        if slug in casou_nome_ou_sigla or item["pontos"] >= LIMIAR_TEMA:
            rotulos.append(slug)
            motivo[slug] = item["motivos"]
            total_pontos += item["pontos"]

    # Regra do "tema com contexto do governo": uma materia que fala do
    # Governo do Estado e tem 1 tema pertence a pasta daquele tema
    # (ex.: "Governo de MT anuncia novo vacino" -> SES).
    if not rotulos:
        contexto_gov = bool(
            re.search(
                r"(governo (?:de mt|do estado de mato grosso|mato grosso)|"
                r"estado de mato grosso|palacio paiaguas|governo mt)",
                limpo,
            )
        )
        if contexto_gov:
            candidatos = [
                (slug, item) for slug, item in pontos.items() if item["pontos"] >= 1
            ]
            if candidatos:
                melhor = max(candidatos, key=lambda par: par[1]["pontos"])
                rotulos.append(melhor[0])
                motivo[melhor[0]] = melhor[1]["motivos"] + ["contexto do Governo do Estado"]
                total_pontos = melhor[1]["pontos"]

    # ordem alfabetica das siglas (estabilidade entre execucoes)
    sigla_por_slug = {s.get("slug"): (s.get("sigla") or "") for s in secretarias}
    rotulos.sort(key=lambda s: (sigla_por_slug.get(s, ""), s))

    # alvos: o governo como um todo e o governador
    alvos = ["governo-mt"]
    if governador:
        termos = [_normalizar(t) for t in governador.get("termos", [])]
        if any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", limpo) for t in termos if len(t) > 3):
            alvos.append("governador")
    if interino:
        termos_i = [_normalizar(t) for t in interino.get("termos", [])]
        if any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", limpo) for t in termos_i if len(t) > 3):
            alvos.append("interino")

    geral = not rotulos
    if geral:
        rotulos = [GERAL]

    # Escopo: separa "governo do Estado" de "outras instituições de MT"
    # (ALMT, câmaras, prefeituras) e de "notícia geral de MT".
    escopo = "geral-mt"
    if rotulos != [GERAL] or "governador" in alvos or "interino" in alvos:
        escopo = "governo-estado"
    elif _instituicoes_mt(limpo):
        escopo = "instituicoes-mt"

    # confianca: saturacao em 8 pontos
    confianca = min(1.0, round(total_pontos / 8.0, 3)) if total_pontos else 0.15

    return {
        "secretarias": rotulos,
        "siglas": [sigla_por_slug.get(s, "") for s in rotulos],
        "alvos": alvos,
        "escopo": escopo,
        "confianca": confianca,
        "motivo": motivo,
        "geral": geral,
    }


# Instituicoes de MT que NAO sao o Executivo estadual
RE_INSTITUICOES_MT = re.compile(
    r"(assembleia legislativa|al\.mt\.gov\.br|camara municipal|camara de cuiaba|"
    r"camara de varzea|prefeitura de cuiaba|prefeitura de varzea|"
    r"universidade federal de mato grosso|ufmt|organizacao de utc|"
    r"tribunal de justica|tjmt|ministerio publico|mp mt)",
)


def _instituicoes_mt(limpo: str) -> bool:
    """True se o texto cita outra instituicao de MT (ALMT, prefeituras, TJ...)."""
    return bool(RE_INSTITUICOES_MT.search(limpo))
