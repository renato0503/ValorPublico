"""Testes do coletor Instagram via navegador (sem rede, com dados simulados).

Cobre: decodificacao de shortcode, extracao de capa (foto/video/carrossel),
normalizacao de comentarios (incluindo respostas), montagem do post, markdown,
conversao para RawItem e gravacao em PNG.
"""
import io
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from scraper.instagram_web import (  # noqa: E402
    extrair_capa_url,
    extrair_imagens,
    extrair_shortcodes_html,
    gravar_png,
    media_id_para_shortcode,
    montar_post,
    parse_comentarios,
    post_para_json,
    post_para_markdown,
    post_para_raw_item,
    shortcode_da_url,
    shortcode_para_media_id,
    tipo_de_midia,
)

_total = 0
_falhas = 0


def check(nome: str, cond: bool, detalhe: str = "") -> None:
    global _total, _falhas
    _total += 1
    if cond:
        print(f"  PASS  {nome}")
    else:
        _falhas += 1
        print(f"  FAIL  {nome}  {detalhe}")


ITEM_VIDEO = {
    "pk": 123456789,
    "id": "123456789_1",
    "code": "DgIPl9rj4Xd",
    "media_type": 2,
    "taken_at": 1730000000,
    "like_count": 397,
    "comment_count": 28,
    "caption": {"text": "MAIS FLUIDEZ NO TRÂNSITO\n\nAs obras começaram."},
    "user": {"username": "govmatogrosso", "full_name": "Governo de Mato Grosso"},
    "image_versions2": {
        "candidates": [
            {"url": "https://cdn.fb/small.jpg", "width": 150, "height": 150},
            {"url": "https://cdn.fb/big.jpg", "width": 1080, "height": 1920},
        ]
    },
}

ITEM_CARROSSEL = {
    "pk": 987,
    "code": "Carrossel1",
    "media_type": 8,
    "carousel_media": [
        {"image_versions2": {"candidates": [{"url": "https://cdn/c1.jpg", "width": 600, "height": 600}]}},
        {"image_versions2": {"candidates": [{"url": "https://cdn/c2.jpg", "width": 600, "height": 600}]}},
    ],
}

PAGINA_COMENTARIOS = {
    "comments": [
        {
            "pk": 1,
            "text": "Vai transferir o gargalo para o trevo do Comper",
            "created_at": 1730000100,
            "comment_like_count": 10,
            "user": {"username": "fulano", "full_name": "Fulano de Tal"},
            "preview_child_comments": [
                {
                    "pk": 2,
                    "text": "concordo",
                    "created_at": 1730000200,
                    "comment_like_count": 1,
                    "user": {"username": "ciclano"},
                }
            ],
        },
        {
            "pk": 3,
            "text": "  ",
            "created_at": None,
            "user": {"username": "beltrano"},
        },
    ],
    "has_more_comments": True,
    "next_min_id": "9",
}


def teste_shortcode() -> None:
    print("== shortcode <-> media id ==")
    check("'A' -> 0", shortcode_para_media_id("A") == "0")
    check("'B' -> 1", shortcode_para_media_id("B") == "1")
    check("'_' -> 63", shortcode_para_media_id("_") == "63")
    check("'BA' -> 64", shortcode_para_media_id("BA") == "64")
    check("'BB' -> 65", shortcode_para_media_id("BB") == "65")
    for code in ("DgIPl9rj4Xd", "Cabc123_-", "XyZ_09aBcDe"):
        volta = media_id_para_shortcode(shortcode_para_media_id(code))
        check(f"roundtrip {code}", volta == code, volta)


def teste_shortcode_da_url() -> None:
    print("== shortcode a partir da URL ==")
    casos = {
        "https://www.instagram.com/p/DgIPl9rj4Xd/": "DgIPl9rj4Xd",
        "https://instagram.com/p/DgIPl9rj4Xd?igsh=abc": "DgIPl9rj4Xd",
        "https://www.instagram.com/reel/ABC123/": "ABC123",
        "https://www.instagram.com/tv/XYZ789/": "XYZ789",
        "https://www.instagram.com/govmatogrosso/": None,
        "https://www.globo.com/p/abc/": None,
        "nao-e-url": None,
    }
    for url, esperado in casos.items():
        obtido = shortcode_da_url(url)
        check(f"{url} -> {esperado}", obtido == esperado, str(obtido))


def teste_capa_e_tipo() -> None:
    print("== capa e tipo de midia ==")
    check("video -> capa maior", extrair_capa_url(ITEM_VIDEO) == "https://cdn.fb/big.jpg")
    check("carrossel -> 1o item", extrair_capa_url(ITEM_CARROSSEL) == "https://cdn/c1.jpg")
    check("sem imagem -> vazio", extrair_capa_url({"media_type": 1}) == "")
    check("tipo 1 -> Foto", tipo_de_midia(1) == "Foto")
    check("tipo 2 -> Video", tipo_de_midia(2) == "Video")
    check("tipo 8 -> Carrossel", tipo_de_midia(8) == "Carrossel")
    check("tipo None -> Desconhecido", tipo_de_midia(None) == "Desconhecido")
    check("imagens de video", extrair_imagens(ITEM_VIDEO) == ["https://cdn.fb/big.jpg"])
    check("imagens de carrossel", extrair_imagens(ITEM_CARROSSEL) == ["https://cdn/c1.jpg", "https://cdn/c2.jpg"])
    check("imagens vazias", extrair_imagens({"media_type": 1}) == [])


def teste_shortcodes_html() -> None:
    print("== shortcodes a partir do HTML do perfil ==")
    html = '{"shortcode":"AAA111"}, {"shortcode":"BBB222"}, {"shortcode":"AAA111"}'
    check("extrai na ordem, sem repetir", extrair_shortcodes_html(html) == ["AAA111", "BBB222"])
    check("html vazio", extrair_shortcodes_html("") == [])


def teste_comentarios() -> None:
    print("== normalizacao de comentarios ==")
    itens = parse_comentarios(PAGINA_COMENTARIOS, "DgIPl9rj4Xd")
    check("3 comentarios (2 + 1 resposta)", len(itens) == 3, str(len(itens)))
    pai = itens[0]
    check("autor do pai", pai["autor"] == "fulano")
    check("curtidas do pai", pai["curtidas"] == 10)
    check("data do pai e datetime UTC", isinstance(pai["criado_em"], datetime) and pai["criado_em"].tzinfo == timezone.utc)
    check("permalink do comentario", pai["permalink"] == "https://www.instagram.com/p/DgIPl9rj4Xd/c/1/")
    filho = itens[1]
    check("resposta aponta para o pai", filho["responde_a"] == "1")
    check("texto da resposta", filho["texto"] == "concordo")


def teste_montar_post() -> None:
    print("== montagem do post ==")
    comentarios = parse_comentarios(PAGINA_COMENTARIOS, "DgIPl9rj4Xd")
    post = montar_post(ITEM_VIDEO, comentarios)
    check("shortcode", post["shortcode"] == "DgIPl9rj4Xd")
    check("autor", post["autor"] == "govmatogrosso")
    check("curtidas", post["curtidas"] == 397)
    check("total comentarios", post["total_comentarios"] == 28)
    check("tipo video", post["tipo_midia"] == "Video")
    check("legenda preservada", post["legenda"].startswith("MAIS FLUIDEZ"))
    check("data publicacao UTC", post["data_publicacao"].tzinfo == timezone.utc)
    check("capa", post["capa_url"] == "https://cdn.fb/big.jpg")
    check("lista de imagens", post["imagens"] == ["https://cdn.fb/big.jpg"])
    check("metadados video", post["metadados"]["video"] is True)
    check("comentarios coletados", post["metadados"]["comentarios_coletados"] == 3)
    check("url canonica", post["url"] == "https://www.instagram.com/p/DgIPl9rj4Xd/")


def teste_saidas() -> None:
    print("== markdown, raw item e json ==")
    post = montar_post(ITEM_VIDEO, parse_comentarios(PAGINA_COMENTARIOS, "DgIPl9rj4Xd"))
    md = post_para_markdown(post)
    check("titulo no markdown", "# govmatogrosso — DgIPl9rj4Xd" in md)
    check("secao descricao", "## Descrição" in md)
    check("secao comentarios", "## Comentários (3)" in md)
    check("autor do comentario", "@fulano" in md)
    check("link do comentario", "/c/1/" in md)

    raw = post_para_raw_item(post, "governo-mt")
    check("plataforma Instagram", raw["plataforma"] == "Instagram")
    check("tipo Postagem", raw["tipo"] == "Postagem")
    check("id_externo", raw["id_externo"] == "DgIPl9rj4Xd")
    check("alcance = curtidas + comentarios", raw["alcance"] == 425, str(raw["alcance"]))
    check("midia com a capa", raw["midia"][0]["url_original"] == "https://cdn.fb/big.jpg")
    check("origem navegador", raw["metadados"]["origem_coleta"] == "navegador")

    texto_json = post_para_json(post)
    check("json serializa data", "2024-10" in texto_json or "taken_at" not in texto_json)
    check("json sem screenshot", "screenshot_png" not in texto_json)


def teste_png() -> None:
    print("== gravacao de capa em PNG ==")
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        print("  SKIP  Pillow indisponivel")
        return
    buffer = io.BytesIO()
    Image.new("RGB", (20, 30), (10, 20, 30)).save(buffer, format="JPEG")
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "capa.png"
        saida = gravar_png(buffer.getvalue(), destino)
        check("arquivo gerado", saida.exists() and saida.suffix == ".png")
        check("assinatura PNG", saida.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")


def main() -> None:
    teste_shortcode()
    teste_shortcode_da_url()
    teste_capa_e_tipo()
    teste_shortcodes_html()
    teste_comentarios()
    teste_montar_post()
    teste_saidas()
    teste_png()
    print(f"\nRESULTADO: {_total - _falhas} passaram, {_falhas} falharam")
    sys.exit(1 if _falhas else 0)


if __name__ == "__main__":
    main()
