"""Coleta posts do Instagram como um humano no navegador (sem instaloader).

Usa o perfil persistente do Chromium/Patchright (conta do proprio dono) e a
API interna do Instagram a partir da pagina ja autenticada. Gera:

  <saida>/<shortcode>/post.json        dados estruturados (pronto p/ RawItem)
  <saida>/<shortcode>/post.md          visao legivel (descricao + comentarios)
  <saida>/<shortcode>/descricao.md     so a legenda
  <saida>/<shortcode>/comentarios.md   so os comentarios
  <saida>/<shortcode>/capa.png         capa do post
  <saida>/<shortcode>/pagina.png       print da pagina (quando possivel)

Com `--continuar`, tambem escreve `fotoN.png` + `fotoN.md` na raiz de `--saida`,
seguindo a numeracao ja existente (o mesmo esquema da coleta manual).

Uso (a partir de `backend/`):
    python scripts/coletar_instagram.py --login
    python scripts/coletar_instagram.py --url https://www.instagram.com/p/DgIPl9rj4Xd/ --continuar
    python scripts/coletar_instagram.py --url URL1 URL2 --saida ../docs/instagram
    python scripts/coletar_instagram.py --perfil govmatogrosso --limite 5 --continuar
    python scripts/coletar_instagram.py --url URL --agente-id governo-mt --json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import BASE_DIR
from core.logger import get_logger
from scraper.instagram_web import (
    BloqueioInstagram,
    InstagramWebColetor,
    gravar_post,
    post_para_markdown,
    post_para_raw_item,
)

logger = get_logger(__name__)

SAIDA_PADRAO = BASE_DIR.parent / "docs" / "instagram"


def _normalizar_urls(bruto: list[str]) -> list[str]:
    saida: list[str] = []
    for valor in bruto:
        for parte in re.split(r"[\s,]+", valor.strip()):
            if parte:
                saida.append(parte)
    return saida


def proximo_indice(pasta: Path) -> int:
    """Proximo numero livre no esquema `fotoN.*` (1 quando nao ha nenhum)."""
    maior = 0
    for arquivo in pasta.glob("foto*"):
        achado = re.match(r"foto(\d+)", arquivo.stem)
        if achado:
            maior = max(maior, int(achado.group(1)))
    return maior + 1


def _escrever_continuacao(
    post: dict, pasta_saida: Path, indice: int, imagens: list[Path | None]
) -> tuple[Path | None, Path]:
    principal: Path | None = None
    for numero, caminho in enumerate(imagens, start=1):
        if caminho is None or not caminho.exists():
            continue
        if numero == 1:
            destino = pasta_saida / f"foto{indice}.png"
        else:
            destino = pasta_saida / f"foto{indice}_{numero}.png"
        if caminho.suffix.lower() != ".png":
            destino = destino.with_suffix(caminho.suffix)
        shutil.copyfile(caminho, destino)
        if numero == 1:
            principal = destino
    if principal is None:
        screenshot = post.get("screenshot_png") or b""
        if screenshot:
            principal = pasta_saida / f"foto{indice}.png"
            principal.write_bytes(screenshot)
    destino_md = pasta_saida / f"foto{indice}.md"
    destino_md.write_text(post_para_markdown(post), encoding="utf-8")
    return principal, destino_md


def _processar_post(
    coletor: InstagramWebColetor,
    post: dict,
    pasta_saida: Path,
    continuar: bool,
    agente_id: str,
) -> dict:
    pasta_post = pasta_saida / (post.get("shortcode") or "semShortcode")
    pasta_post.mkdir(parents=True, exist_ok=True)
    urls = post.get("imagens") or ([post.get("capa_url")] if post.get("capa_url") else [])
    imagens: list[Path | None] = []
    for numero, url in enumerate(urls, start=1):
        nome = "capa.png" if numero == 1 else f"imagem{numero}.png"
        imagens.append(coletor.baixar_imagem(url, pasta_post / nome))
    baixadas = [caminho for caminho in imagens if caminho is not None]
    resultado = {
        "shortcode": post.get("shortcode"),
        "url": post.get("url"),
        "autor": post.get("autor"),
        "comentarios": len(post.get("comentarios") or []),
        "capa": str(baixadas[0]) if baixadas else "",
        "imagens": [str(caminho) for caminho in baixadas],
        "pasta": str(pasta_post),
    }
    if continuar:
        indice = proximo_indice(pasta_saida)
        png, md = _escrever_continuacao(post, pasta_saida, indice, imagens)
        resultado["foto_png"] = str(png) if png else ""
        resultado["foto_md"] = str(md)
    if agente_id:
        (pasta_post).mkdir(parents=True, exist_ok=True)
        (pasta_post / "raw_item.json").write_text(
            json.dumps(
                post_para_raw_item(post, agente_id),
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    gravar_post(post, pasta_post)
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta posts do Instagram pelo navegador.")
    parser.add_argument("--login", action="store_true", help="abre o navegador para logar uma vez")
    parser.add_argument("--url", nargs="+", default=[], help="uma ou mais URLs/shortcodes de post")
    parser.add_argument("--perfil", default="", help="usuario do perfil (sem @) para pegar os ultimos posts")
    parser.add_argument("--limite", type=int, default=5, help="quantos posts novos do perfil (com --perfil)")
    parser.add_argument("--pular", nargs="*", default=[], help="shortcodes a ignorar")
    parser.add_argument("--saida", default=str(SAIDA_PADRAO))
    parser.add_argument("--continuar", action="store_true", help="escreve fotoN.png/fotoN.md na raiz de --saida")
    parser.add_argument("--agente-id", default="", help="preenche raw_item.json para a ingestao")
    parser.add_argument("--max-comentarios", type=int, default=300)
    parser.add_argument("--max-paginas", type=int, default=12)
    parser.add_argument("--sem-screenshot", action="store_true")
    parser.add_argument("--visivel", action="store_true", help="mostra o navegador durante a coleta")
    parser.add_argument("--pausa-min", type=float, default=8.0, help="pausa minima entre paginas de comentarios")
    parser.add_argument("--pausa-max", type=float, default=20.0, help="pausa maxima entre paginas de comentarios")
    parser.add_argument("--pausa-posts-min", type=float, default=30.0, help="pausa minima entre posts")
    parser.add_argument("--pausa-posts-max", type=float, default=90.0, help="pausa maxima entre posts")
    parser.add_argument("--json", action="store_true", help="imprime o resumo em JSON")
    args = parser.parse_args()

    pasta_saida = Path(args.saida).expanduser().resolve()
    pasta_saida.mkdir(parents=True, exist_ok=True)

    coletor = InstagramWebColetor(
        headless=not args.visivel,
        pausa_min=args.pausa_min,
        pausa_max=args.pausa_max,
        pausa_posts_min=args.pausa_posts_min,
        pausa_posts_max=args.pausa_posts_max,
    )

    if args.login:
        try:
            coletor.login_interativo()
        finally:
            coletor.fechar()
        return 0

    urls = _normalizar_urls(args.url)
    if not urls and not args.perfil:
        parser.error("informe --url, --perfil ou --login")

    resumo: dict = {
        "saida": str(pasta_saida),
        "iniciado_em": datetime.now(timezone.utc).isoformat(),
        "posts": [],
        "erros": [],
    }
    try:
        coletor.abrir()
        try:
            if args.perfil:
                logger.info("Coletando @%s (ate %d posts)...", args.perfil, args.limite)
                posts = coletor.coletar_perfil(
                    args.perfil,
                    limite=args.limite,
                    max_comentarios=args.max_comentarios,
                    max_paginas=args.max_paginas,
                    pular=set(args.pular),
                )
            else:
                posts = []
                for indice, url in enumerate(urls, start=1):
                    logger.info("[%d/%d] %s", indice, len(urls), url)
                    if indice > 1:
                        coletor._pausa_posts()
                    posts.append(
                        coletor.coletar_post(
                            url,
                            max_comentarios=args.max_comentarios,
                            max_paginas=args.max_paginas,
                            com_screenshot=not args.sem_screenshot,
                        )
                    )
            for post in posts:
                resumo["posts"].append(
                    _processar_post(
                        coletor, post, pasta_saida, args.continuar, args.agente_id
                    )
                )
        finally:
            coletor.fechar()
    except BloqueioInstagram as exc:
        if exc.tipo.startswith("login"):
            logger.error(
                "Instagram pediu login. Rode uma vez: "
                "python scripts/coletar_instagram.py --login"
            )
        else:
            logger.error("Instagram bloqueou (%s). Pare e tente mais tarde.", exc.tipo)
        resumo["erros"].append({"tipo": "bloqueio", "detalhe": str(exc)})
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha na coleta: %s", exc)
        resumo["erros"].append({"tipo": "erro", "detalhe": str(exc)})

    resumo["finalizado_em"] = datetime.now(timezone.utc).isoformat()
    resumo["total_posts"] = len(resumo["posts"])
    if args.json:
        print(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"\n=== COLETA INSTAGRAM ===\nposts: {resumo['total_posts']} | erros: {len(resumo['erros'])}")
        for item in resumo["posts"]:
            print(f"  {item['shortcode']}: {item['comentarios']} comentarios -> {item['pasta']}")
        for erro in resumo["erros"]:
            print(f"  ERRO {erro['tipo']}: {erro['detalhe']}")
    return 0 if not resumo["erros"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
