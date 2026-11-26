"""Saneamento da base do Governo de MT (plano 22, sprint S0).

Duas regras, usadas na coleta, na publicação e nas métricas:

* ``limpar_texto``: desfaz entidades HTML (inclusive as escapadas duas vezes,
  como ``&amp;nbsp;``) e apaga sobras como ``nbsp;`` que o agregador deixa
  nos títulos.
* ``veiculo_fora_de_mt``: o agregador mistura veículos de Mato Grosso do Sul
  (Assembleia, Polícia Civil e Bombeiros de MS...) porque o texto tem "MT"
  ou "Mato Grosso". Esses itens não são do Governo de MT.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path

# Veículos (ou trechos de nome) que indicam outro estado. Comparação feita
# sem acento e em minúsculas.
_FORA_DE_MT = re.compile(
    r"mato grosso do sul"
    r"|(?<![a-z0-9])ms(?![a-z0-9])"
    r"|campo grande"
    r"|dourados"
    r"|caarapo"
    r"|tres lagoas"
    r"|corumba"
    r"|capital ?news"
    r"|midiamax",
)
# titulo que fala de MS sem nenhuma marca de MT ("MT e MS divergem..." fica)
_TITULO_MS = re.compile(r"(?i:mato grosso do sul)|(?<![A-Za-z])MS(?![A-Za-z])|-MS")
_MARCA_MT = re.compile(
    r"(?<![A-Za-z])MT(?![A-Za-z])|mato grosso(?! do sul)|cuiab|pivetta|max russi|paiagu|mauro mendes",
    re.IGNORECASE,
)
_SOBRA_NBSP = re.compile(r"&?\bnbsp\b;?", re.IGNORECASE)
_ESPACOS = re.compile(r"\s+")


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def limpar_texto(texto: str | None) -> str:
    """Título/resumo sem entidades HTML, sem ``nbsp`` e com espaços normais."""
    if not texto:
        return ""
    limpo = html.unescape(html.unescape(texto))
    limpo = limpo.replace("\xa0", " ")
    limpo = _SOBRA_NBSP.sub(" ", limpo)
    return _ESPACOS.sub(" ", limpo).strip()


def veiculo_fora_de_mt(veiculo: str | None) -> bool:
    """True quando o nome do veículo indica outro estado (sobretudo MS)."""
    return bool(_FORA_DE_MT.search(_sem_acento(veiculo or "")))


def titulo_so_de_ms(titulo: str | None) -> bool:
    """Manchete sobre Mato Grosso do Sul, sem nada de MT."""
    t = titulo or ""
    sem_ms = re.sub(r"mato grosso do sul", " ", t, flags=re.IGNORECASE)
    return bool(_TITULO_MS.search(t)) and not _MARCA_MT.search(sem_ms)


def sanear_itens(itens: list[dict]) -> tuple[list[dict], list[dict]]:
    """Limpa título/resumo e separa os itens de fora de MT.

    Devolve ``(validos, removidos)``. Não altera a ordem dos válidos.
    """
    validos: list[dict] = []
    removidos: list[dict] = []
    for item in itens:
        if veiculo_fora_de_mt(item.get("veiculo")) or titulo_so_de_ms(item.get("titulo")):
            removidos.append(item)
            continue
        for campo in ("siglas", "secretarias", "municipios", "alvos"):
            if isinstance(item.get(campo), list):
                item[campo] = [v for v in item[campo] if v]
        item["titulo"] = limpar_texto(item.get("titulo"))
        if item.get("resumo"):
            item["resumo"] = limpar_texto(item.get("resumo"))
        if "municipios" not in item:
            from processing.municipios_mt import detectar

            item["municipios"] = detectar(f"{item['titulo']} {item.get('resumo') or ''}")
        validos.append(item)
    return validos, removidos


def id_da_noticia(item: dict) -> str:
    """Mesmo id usado no Firestore (md5 da URL, ou do titulo sem URL)."""
    base = item.get("url") or item.get("titulo") or ""
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def linhas_da_base(pasta: Path, arquivo: Path | None = None) -> list[dict]:
    """Itens brutos da base do Governo.

    Com ``arquivo``: so aquele JSONL. Sem: a uniao de todos os
    ``noticias-*.jsonl`` da pasta (inclusive subpastas de carga historica),
    sem repeticao; a coleta mais recente prevalece.
    """
    arquivos = [arquivo] if arquivo else sorted(
        Path(pasta).rglob("noticias-*.jsonl"), key=lambda p: p.name
    )
    por_id: dict[str, dict] = {}
    for caminho in arquivos:
        for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
            if linha.strip():
                item = json.loads(linha)
                por_id[id_da_noticia(item)] = item
    return list(por_id.values())
