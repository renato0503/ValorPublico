"""Testes do pipeline de imagens (plano 18 §8) — I0–I5.

Roda standalone (sem pytest):
    python tests/teste_imagem.py

Cobre:
  - guarda anti-SSRF (IP privado/loopback/link local);
  - recusa de arquivo grande e de Content-Type que nao e imagem;
  - EXIF/GPS removido, WebP 640/160 gerados, pHash estavel entre versions;
  - OCR num card sintetico ("VOTE 15");
  - tipo de peca e reuso (K-74);
  - agregado da galeria < 1 MiB.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerra_nucleo.processing import imagem  # noqa: E402

PASSOU: list[str] = []
FALHOU: list[str] = []


def checar(desc: str, condicao: bool, extra: str = "") -> None:
    if condicao:
        PASSOU.append(desc)
        print(f"  PASS  {desc}")
    else:
        FALHOU.append(desc)
        print(f"  FAIL  {desc} {extra}")


def _criar_card(texto: str = "VOTE 15", largura: int = 640, altura: int = 400, exif_gps: bool = False):
    """Cria uma imagem sintetica (tipo card de campanha)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (largura, altura), (200, 30, 40))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, largura - 10, altura - 10], outline=(255, 255, 255), width=4)
    draw.text((40, altura // 2 - 10), texto, fill=(255, 255, 255))
    buffer = io.BytesIO()
    formato = "JPEG"
    img.save(buffer, formato, quality=90)
    dados = buffer.getvalue()
    if exif_gps:
        from PIL import Image as PILImage

        img2 = PILImage.open(io.BytesIO(dados))
        exif = PILImage.Exif()
        # Tag de texto com coordenada (simula metadado de localizacao gravado).
        exif[0x010E] = "GPS: -15.601, -56.097"
        exif[0x0131] = "CerraClippingTest"
        buffer2 = io.BytesIO()
        img2.save(buffer2, formato, quality=90, exif=exif)
        dados = buffer2.getvalue()
    return dados


def main() -> int:
    print("== guarda anti-SSRF ==")
    checar("recusa loopback", not imagem.url_segura("http://127.0.0.1/x"))
    checar("recusa link-local", not imagem.url_segura("http://169.254.169.254/latest/meta-data"))
    checar("recusa privado 10.x", not imagem.url_segura("http://10.0.0.5/x"))
    checar("recusa privado 192.168.x", not imagem.url_segura("http://192.168.0.1/x"))
    checar("recusa file://", not imagem.url_segura("file:///etc/passwd"))
    checar("recusa ftp://", not imagem.url_segura("ftp://exemplo.com/x.png"))
    checar("aceita host publico", imagem.url_segura("https://g1.globo.com/mat/g1.jpg"))

    print("== download recusado ==")
    try:
        imagem.baixar("http://127.0.0.1/imagem.png")
        checar("recusa download de IP privado", False)
    except imagem.DownloadRecusado:
        checar("recusa download de IP privado", True)

    print("== processamento local ==")
    dados = _criar_card(exif_gps=True)
    pasta = Path(__file__).resolve().parent / "_tmp_imagens"
    resultado = imagem.processar_imagem(dados, pasta=pasta, nome="card_teste")
    checar("imagem processada", bool(resultado.phash), resultado.motivo)
    checar("pHash com 16 chars", len(resultado.phash) == 16, resultado.phash)
    checar("sha256 preenchido", len(resultado.sha256) == 64)
    checar("dimensoes lidas", resultado.largura == 640 and resultado.altura == 400)
    checar("WebP 640 gerado", Path(resultado.webp_640).exists())
    checar("WebP 160 gerado", Path(resultado.webp_160).exists())
    checar("base64 160 presente", len(resultado.base64_160) > 100)
    checar("EXIF marcado como removido", resultado.exif_removido)

    from PIL import Image

    with Image.open(resultado.webp_160) as mini:
        checar("miniatura tem 160 px de lado", max(mini.size) <= 160, str(mini.size))
        sem_exif = not mini.getexif()
    checar("miniatura sem EXIF", sem_exif)

    print("== pHash entre versoes ==")
    # Mesma imagem, re-encodada com outra qualidade -> mesmo pHash.
    reencode = io.BytesIO()
    with Image.open(io.BytesIO(dados)) as img:
        img.save(reencode, "JPEG", quality=55)
    r2 = imagem.processar_imagem(reencode.getvalue(), pasta=pasta, nome="card_reencode")
    checar(
        "mesma imagem re-encodada -> pHash igual",
        imagem.mesma_imagem(resultado.phash, r2.phash),
        f"{resultado.phash} vs {r2.phash}",
    )
    outra = _criar_card(texto="SAUDE NA CIDADE")
    r3 = imagem.processar_imagem(outra, pasta=pasta, nome="card_outro")
    checar("imagem diferente -> pHash distinto", not imagem.mesma_imagem(resultado.phash, r3.phash))

    print("== OCR ==")
    res_ocr = imagem.ocr(dados)
    texto = res_ocr.get("texto", "").upper()
    checar("OCR leu 'VOTE'", "VOTE" in texto, texto[:80])
    checar("OCR devolveu caixas", len(res_ocr.get("caixas", [])) > 0)
    checar("OCR tem confianca", res_ocr.get("conf", 0) > 0)

    print("== tipo de peca ==")
    tipo = imagem.classificar_tipo(dados)
    checar(
        "tipo de peca reconhecido",
        tipo.get("tipo_peca") in imagem.TIPOS_PECA,
        str(tipo.get("motivo")),
    )
    checar("rotulo amigavel presente", bool(tipo.get("rotulo")))

    print("== reuso (K-74) ==")
    checar("imagem nova nao e reciclada", not imagem.imagem_reciclada("2026-11-24T00:00:00+00:00"))
    checar(
        "imagem antiga e reciclada",
        imagem.imagem_reciclada("2026-01-01T00:00:00+00:00", dias_limite=30),
    )

    print("== galeria no agregado (< 1 MiB) ==")
    galeria = [
        {
            "thumb": resultado.base64_160[:800],
            "rede": "Instagram",
            "tipo": "card_com_texto",
            "resumo": "Card com texto sobre saude",
        }
        for _ in range(24)
    ]
    import json

    tamanho = len(json.dumps(galeria, ensure_ascii=False).encode("utf-8"))
    checar("galeria de 24 itens cabe em 1 MiB", tamanho < 1024 * 1024, f"{tamanho} bytes")

    # limpeza
    for arquivo in pasta.glob("*"):
        arquivo.unlink()
    if pasta.exists():
        pasta.rmdir()

    print()
    print(f"RESULTADO: {len(PASSOU)} passaram, {len(FALHOU)} falharam")
    if FALHOU:
        for item in FALHOU:
            print("  FALHOU:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
