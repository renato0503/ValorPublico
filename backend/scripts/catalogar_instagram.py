"""Cataloga a coleta do Instagram (manual + automática) para o Valor Público.

Le `docs/instagram` (pastas `<shortcode>/post.json` e arquivos `fotoN.md/png`) e
cruza os dois formatos, detectando cópias e duplicados. Gera:

  catalogo.json                 inventário completo (posts, cópias, duplicados)
  CATALOGO.md                   tabela legível + mapeamento p/ o Valor Público
  ingestao_valorpublico.jsonl   um RawItem por post e por comentário

Mapeamento no Valor Público (mesmo caminho do `scraper/instagram_scraper.py`):

  agentes_publicos/<agente_id>/clippings/<plataforma>_<id_externo>

  * post      -> tipo "Postagem", id_externo = shortcode
  * comentário -> tipo "Comentario", id_externo = id do comentário
  * `midia[]`  guarda o `arquivo_local` (PNG já baixado) e a `url_original`

Uso (a partir de `backend/`):
    python scripts/catalogar_instagram.py
    python scripts/catalogar_instagram.py --agente-id governo-mt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import BASE_DIR
from core.logger import get_logger

logger = get_logger(__name__)

RAIZ_PADRAO = BASE_DIR.parent / "docs" / "instagram"
AGENTE_PADRAO = "governo-mt"
PERFIL = "govmatogrosso"
AGENTE_GOVERNADOR = "governador-otaviano-pivetta"
AGENTE_POR_AUTOR = {
    "govmatogrosso": "governo-mt",
    "otavianopivetta": AGENTE_GOVERNADOR,
}
FONTE_POR_AUTOR = {
    "govmatogrosso": "govmt",
    "otavianopivetta": "governador",
}

RE_URL_POST = re.compile(r"-\s*URL:\s*https://www\.instagram\.com/p/([A-Za-z0-9_-]+)/")
RE_PERMALINK = re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)/c/")
RE_FOTO = re.compile(r"foto(\d+)(?:_(\d+))?$")
RE_TIMESTAMP = re.compile(r"^\s*\d+\s*(?:min|h|d)\s*$")


def _sem_acento(texto: str) -> str:
    import unicodedata

    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(texto)).strip()


def _similar(a: str, b: str) -> float:
    a, b = _normalizar(a)[:300], _normalizar(b)[:300]
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _iso(valor) -> str | None:
    if not valor:
        return None
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor).isoformat()
        except ValueError:
            return valor
    return valor.isoformat()


def _rel(caminho: Path | None, raiz: Path) -> str:
    if caminho is None:
        return ""
    try:
        return str(caminho.relative_to(raiz.parent if raiz.name == "instagram" else raiz))
    except ValueError:
        return str(caminho)


# ----------------------------------------------------------------------
# Leitura dos dois formatos
# ----------------------------------------------------------------------
def ler_post_json(pasta: Path) -> dict | None:
    arquivo = pasta / "post.json"
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("post.json ilegivel em %s: %s", pasta.name, exc)
        return None
    return dados


def legenda_manual(texto: str) -> str:
    """Extrai a legenda dos .md feitos à mão (leitor de tela ou markdown)."""
    if "## Descrição" in texto:
        corpo = texto.split("## Descrição", 1)[1].split("## Comentários", 1)[0]
        return corpo.strip()
    linhas = texto.splitlines()
    inicio = 0
    for indice, linha in enumerate(linhas):
        if linha.strip().startswith("Curtido por"):
            inicio = indice + 1
            break
    else:
        for indice, linha in enumerate(linhas):
            limpa = linha.strip()
            if limpa.startswith("* #") or limpa.startswith("#"):
                inicio = indice
                break
    fim = len(linhas)
    for indice in range(inicio, len(linhas)):
        if RE_TIMESTAMP.match(linhas[indice]):
            fim = indice
            break
    corpo = "\n".join(linhas[inicio:fim])
    corpo = re.sub(r"^\s*\*\s?", "", corpo, flags=re.M)
    corpo = re.sub(r"(?m)^\s*#+\s*", "", corpo)
    return re.sub(r"\n{3,}", "\n\n", corpo).strip()


def ler_md(caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    curto = RE_URL_POST.search(texto)
    if not curto:
        curto = RE_PERMALINK.search(texto)
    shortcode = curto.group(1) if curto else ""
    url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""
    permalinks = len(RE_PERMALINK.findall(texto))
    return {
        "shortcode": shortcode,
        "url": url,
        "legenda": legenda_manual(texto),
        "permalinks": permalinks,
    }


def agrupar_flat(raiz: Path) -> dict[int, dict]:
    grupos: dict[int, dict] = {}
    for arquivo in raiz.glob("foto*"):
        achado = RE_FOTO.match(arquivo.stem)
        if not achado:
            continue
        numero = int(achado.group(1))
        sub = int(achado.group(2) or 1)
        grupo = grupos.setdefault(numero, {"md": None, "imagens": []})
        if arquivo.suffix.lower() in (".md", ".txt") or arquivo.suffix == "":
            grupo["md"] = arquivo
        elif arquivo.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            grupo["imagens"].append((sub, arquivo))
    for grupo in grupos.values():
        grupo["imagens"] = [imagem for _, imagem in sorted(grupo["imagens"])]
    return dict(sorted(grupos.items()))


# ----------------------------------------------------------------------
# Catálogo
# ----------------------------------------------------------------------
def construir(raiz: Path, agente_id: str) -> dict:
    posts: dict[str, dict] = {}
    for pasta in sorted(raiz.iterdir()):
        if not pasta.is_dir():
            continue
        dados = ler_post_json(pasta)
        if not dados or not dados.get("shortcode"):
            continue
        shortcode = dados["shortcode"]
        imagens = sorted(pasta.glob("*.png"))
        capa = pasta / "capa.png"
        autor = dados.get("autor") or PERFIL
        posts[shortcode] = {
            "shortcode": shortcode,
            "url": dados.get("url") or f"https://www.instagram.com/p/{shortcode}/",
            "origem": "scraper",
            "fonte": FONTE_POR_AUTOR.get(autor, "governador"),
            "agente_id": AGENTE_POR_AUTOR.get(autor, AGENTE_GOVERNADOR),
            "autor": autor,
            "autor_nome": dados.get("autor_nome") or "",
            "data_publicacao": _iso(dados.get("data_publicacao")),
            "tipo_midia": dados.get("tipo_midia") or "",
            "curtidas": int(dados.get("curtidas") or 0),
            "total_comentarios": int(dados.get("total_comentarios") or 0),
            "comentarios_coletados": len(dados.get("comentarios") or []),
            "legenda": dados.get("legenda") or "",
            "capa": _rel(capa, raiz) if capa.exists() else _rel(imagens[0], raiz) if imagens else "",
            "imagens": [_rel(arquivo, raiz) for arquivo in imagens],
            "pasta": _rel(pasta, raiz),
            "post_json": _rel(pasta / "post.json", raiz),
            "foto_flat": "",
            "duplicado_de": "",
            "status": "pronto",
            "_comentarios": dados.get("comentarios") or [],
            "_capa_url": dados.get("capa_url") or "",
            "_urls_imagens": dados.get("imagens")
            or ([dados.get("capa_url")] if dados.get("capa_url") else []),
        }

    copias: list[dict] = []
    manuais: list[dict] = []
    for numero, grupo in agrupar_flat(raiz).items():
        md = grupo.get("md")
        info = ler_md(md) if md else {"shortcode": "", "url": "", "legenda": "", "permalinks": 0}
        imagens = [_rel(arquivo, raiz) for arquivo in grupo.get("imagens") or []]
        if info["shortcode"] and info["shortcode"] in posts:
            posts[info["shortcode"]]["foto_flat"] = f"foto{numero}"
            copias.append(
                {
                    "foto": f"foto{numero}",
                    "shortcode": info["shortcode"],
                    "capa": imagens[0] if imagens else "",
                    "imagens": imagens,
                    "md": _rel(md, raiz) if md else "",
                }
            )
            continue
        manuais.append(
            {
                "foto": f"foto{numero}",
                "numero": numero,
                "shortcode": info["shortcode"],
                "url": info["url"],
                "origem": "manual",
                "fonte": "govmt",
                "agente_id": AGENTE_POR_AUTOR["govmatogrosso"],
                "autor": PERFIL,
                "autor_nome": "",
                "data_publicacao": None,
                "tipo_midia": "",
                "curtidas": 0,
                "total_comentarios": info["permalinks"],
                "comentarios_coletados": 0,
                "comentarios_no_md": info["permalinks"],
                "legenda": info["legenda"],
                "capa": imagens[0] if imagens else "",
                "imagens": imagens,
                "pasta": "",
                "post_json": "",
                "foto_flat": f"foto{numero}",
                "duplicado_de": "",
                "status": "manual_sem_estrutura",
                "_comentarios": [],
                "_capa_url": "",
                "_urls_imagens": [],
            }
        )

    duplicados: list[dict] = []
    for manual in manuais:
        if manual["shortcode"] and manual["shortcode"] in posts:
            manual["duplicado_de"] = manual["shortcode"]
            manual["status"] = "duplicado"
            duplicados.append(manual)
            continue
        melhor, nota = "", 0.0
        for shortcode, post in posts.items():
            valor = _similar(manual["legenda"], post["legenda"])
            if valor > nota:
                melhor, nota = shortcode, valor
        if melhor and nota >= 0.6:
            manual["duplicado_de"] = melhor
            manual["status"] = "duplicado"
            duplicados.append(manual)
        else:
            posts[f"manual_foto{manual['numero']}"] = manual

    por_fonte: dict[str, dict] = {}
    for post in posts.values():
        item = por_fonte.setdefault(post["fonte"], {"posts": 0, "comentarios": 0})
        item["posts"] += 1
        item["comentarios"] += post["comentarios_coletados"]

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "raiz": str(raiz),
        "agente_id_sugerido": agente_id,
        "perfil": PERFIL,
        "totais": {
            "pastas_estruturadas": len([p for p in posts.values() if p["origem"] == "scraper"]),
            "fotos_flat": len(agrupar_flat(raiz)),
            "posts_unicos": len(posts),
            "duplicados": len(duplicados),
            "copias_flat": len(copias),
            "comentarios_estruturados": sum(
                p["comentarios_coletados"] for p in posts.values() if p["origem"] == "scraper"
            ),
            "imagens": sum(len(p["imagens"]) for p in posts.values()),
            "por_fonte": por_fonte,
        },
        "posts": sorted(
            posts.values(),
            key=lambda p: (p["data_publicacao"] or "", p["shortcode"]),
            reverse=True,
        ),
        "copias_flat": sorted(copias, key=lambda c: c["foto"]),
        "duplicados": sorted(duplicados, key=lambda d: d["foto"]),
    }


def registros_ingestao(catalogo: dict, agente_id: str) -> list[dict]:
    registros: list[dict] = []
    for post in catalogo["posts"]:
        id_externo = post["shortcode"] or post["foto_flat"]
        urls = post.get("_urls_imagens") or []
        midia = [
            {
                "url_original": urls[indice] if indice < len(urls) else "",
                "origem": "api" if post["origem"] == "scraper" else "screenshot",
                "ordem": indice,
                "arquivo_local": caminho,
            }
            for indice, caminho in enumerate(post["imagens"])
        ]
        registros.append(
            {
                "agente_id": post.get("agente_id") or agente_id,
                "id_externo": id_externo,
                "plataforma": "Instagram",
                "tipo": "Postagem",
                "texto_limpo": post["legenda"],
                "data_publicacao": post["data_publicacao"],
                "autor": post["autor"],
                "url": post["url"],
                "alcance": post["curtidas"] + post["total_comentarios"],
                "metadados": {
                    "curtidas": post["curtidas"],
                    "comentarios": post["total_comentarios"],
                    "comentarios_coletados": post["comentarios_coletados"],
                    "tipo_midia": post["tipo_midia"],
                    "origem_coleta": "navegador" if post["origem"] == "scraper" else "manual",
                    "foto_flat": post["foto_flat"],
                    "pasta_local": post["pasta"],
                },
                "midia": midia,
            }
        )
        for comentario in post.get("_comentarios") or []:
            registros.append(
                {
                    "agente_id": post.get("agente_id") or agente_id,
                    "id_externo": str(comentario.get("id")),
                    "plataforma": "Instagram",
                    "tipo": "Comentario",
                    "texto_limpo": comentario.get("texto") or "",
                    "data_publicacao": _iso(comentario.get("criado_em")),
                    "autor": comentario.get("autor") or "",
                    "url": post["url"],
                    "alcance": int(comentario.get("curtidas") or 0),
                    "metadados": {
                        "post_shortcode": post["shortcode"],
                        "responde_a": comentario.get("responde_a") or "",
                        "permalink": comentario.get("permalink") or "",
                        "origem_coleta": "navegador",
                    },
                    "midia": [],
                }
            )
    return registros


# ----------------------------------------------------------------------
# Saída
# ----------------------------------------------------------------------
def escrever_markdown(catalogo: dict, destino: Path) -> None:
    totais = catalogo["totais"]
    linhas = [
        "# Catálogo — Instagram (govmt + governador)",
        "",
        f"Gerado em: {catalogo['gerado_em']}",
        "",
        "## Totais",
        "",
        f"- Pastas estruturadas (coletor): **{totais['pastas_estruturadas']}**",
        f"- Arquivos `fotoN` (manuais + cópias): **{totais['fotos_flat']}**",
        f"- Posts únicos: **{totais['posts_unicos']}**",
        f"- Cópias `fotoN` de posts já estruturados: **{totais['copias_flat']}**",
        f"- Duplicados (ex.: `foto2` = `DgIPl9rj4Xd`): **{totais['duplicados']}**",
        f"- Comentários estruturados: **{totais['comentarios_estruturados']}**",
        f"- Imagens locais: **{totais['imagens']}**",
        "",
        "### Por fonte",
        "",
    ]
    for chave, valor in sorted((totais.get("por_fonte") or {}).items()):
        linhas.append(
            f"- **{chave}** ({AGENTE_POR_AUTOR.get('govmatogrosso') if chave == 'govmt' else AGENTE_GOVERNADOR}): "
            f"{valor['posts']} posts, {valor['comentarios']} comentários"
        )
    linhas += [
        "",
        "## Posts",
        "",
        "| # | shortcode | fonte | foto | data | tipo | curtidas | coments | coletados | origem | status |",
        "|---|-----------|-------|------|------|------|---------:|--------:|----------:|--------|--------|",
    ]
    for indice, post in enumerate(catalogo["posts"], start=1):
        linhas.append(
            f"| {indice} | {post['shortcode'] or '—'} | {post['fonte']} | {post['foto_flat'] or '—'} | "
            f"{(post['data_publicacao'] or '—')[:10]} | {post['tipo_midia'] or '—'} | "
            f"{post['curtidas']} | {post['total_comentarios']} | "
            f"{post['comentarios_coletados']} | {post['origem']} | {post['status']} |"
        )
    if catalogo["duplicados"]:
        linhas += ["", "## Duplicados", ""]
        for dup in catalogo["duplicados"]:
            linhas.append(
                f"- `{dup['foto']}` → já existe como `{dup['duplicado_de']}` "
                f"(status: {dup['status']})"
            )
    linhas += [
        "",
        "## Para onde vai no Valor Público",
        "",
        "- **govmt** (`govmatogrosso`) → agente `governo-mt` → `ingestao_govmt.jsonl`",
        f"- **governador** (`otavianopivetta`) → agente `{AGENTE_GOVERNADOR}` → `ingestao_governador.jsonl`",
        "- Arquivo com todos os registros: `ingestao_valorpublico.jsonl` (cada linha traz o próprio `agente_id`).",
        "- Coleção: `agentes_publicos/<agente_id>/clippings`.",
        "- Documento: `<plataforma>_<id_externo>` (ex.: `Instagram_DgFiL-NjZsV`).",
        "- Post → `tipo = Postagem`; comentário → `tipo = Comentario` (id = id do comentário).",
        "- `metadados` guarda curtidas, total de comentários, coletados, tipo de mídia e origem.",
        "- `midia[]` guarda `arquivo_local` (PNG já baixado) e `url_original` (CDN expira).",
        "- Depois da gravação, rodar o enriquecimento (menção, trecho, compliance, radar, AVPE).",
        "",
    ]
    destino.write_text("\n".join(linhas), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cataloga a coleta do Instagram.")
    parser.add_argument("--raiz", default=str(RAIZ_PADRAO))
    parser.add_argument("--agente-id", default=AGENTE_PADRAO)
    args = parser.parse_args()

    raiz = Path(args.raiz).expanduser().resolve()
    if not raiz.exists():
        logger.error("Pasta inexistente: %s", raiz)
        return 2

    catalogo = construir(raiz, args.agente_id)
    registros = registros_ingestao(catalogo, args.agente_id)

    limpo = {
        **catalogo,
        "posts": [
            {chave: valor for chave, valor in post.items() if not chave.startswith("_")}
            for post in catalogo["posts"]
        ],
    }
    (raiz / "catalogo.json").write_text(
        json.dumps(limpo, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    escrever_markdown(catalogo, raiz / "CATALOGO.md")
    with (raiz / "ingestao_valorpublico.jsonl").open("w", encoding="utf-8") as arquivo:
        for registro in registros:
            arquivo.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")

    por_agente: dict[str, list[dict]] = {}
    for registro in registros:
        por_agente.setdefault(registro["agente_id"], []).append(registro)
    nomes_arquivo = {
        "governo-mt": "ingestao_govmt.jsonl",
        AGENTE_GOVERNADOR: "ingestao_governador.jsonl",
    }
    for agente, itens in sorted(por_agente.items()):
        nome = nomes_arquivo.get(agente, f"ingestao_{agente}.jsonl")
        with (raiz / nome).open("w", encoding="utf-8") as arquivo:
            for registro in itens:
                arquivo.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")

    totais = catalogo["totais"]
    print("\n=== CATÁLOGO INSTAGRAM ===")
    print(f"posts únicos: {totais['posts_unicos']} | comentários: {totais['comentarios_estruturados']}")
    print(f"cópias flat: {totais['copias_flat']} | duplicados: {totais['duplicados']}")
    for chave, valor in sorted((totais.get("por_fonte") or {}).items()):
        print(f"  {chave}: {valor['posts']} posts, {valor['comentarios']} comentários")
    print(f"registros p/ ingestão: {len(registros)}")
    print(f"saída: {raiz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
