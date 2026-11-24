"""Imagens dos posts: captura, download seguro, WebP+pHash, OCR e tipo de peca.

Plano 18. Fases I0–I5.

I0  Baixar (requests, timeout 10 s, <= 8 MB, Content-Type image/*, guarda
    anti-SSRF, `Image.verify()`, remocao de EXIF/GPS) e gerar WebP 640 px (~40 KB)
    e 160 px (~6 KB) + sha256 + pHash.
I1  OCR (RapidOCR, ONNX, CPU) com caixas normalizadas.
I2  Tipo de peca (open_clip zero-shot) + vetor 512-d.
I3  Descricao e sinais via VLM local (Ollama, saida JSON).
I4  Reconhecimento facial (YuNet + face_recognition/DeepFace).
I5  Riscos (compliance), reuso por pHash e credencial C2PA.

Regras do dono (24/11/2026): rostos de terceiros PODEM ser exibidos (nao ha
mais desfoque obrigatorio) e o reconhecimento facial vale tambem para os demais
agentes cadastrados. O que continua proibido: montar ficha individual de
cidadao ou lista de opositores a partir dos rostos.
"""

from __future__ import annotations

import base64
import hashlib
import io
import ipaddress
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from cerra_nucleo.core.logger import get_logger

logger = get_logger(__name__)

TAMANHO_MAXIMO = 8 * 1024 * 1024  # 8 MB
TIMEOUT_DOWNLOAD = 10.0
LARGURA_640 = 640
LARGURA_160 = 160

# Tipos de peca reconhecidos (rotulo, prompt do CLIP, descricao amigavel).
TIPOS_PECA: dict[str, dict[str, str]] = {
    "card_com_texto": {
        "rotulo": "Card com texto",
        "prompt": "a campaign card with big text, a political graphic with words",
        "descricao": "Uma arte com texto grande (card de campanha, grafico ou recado).",
    },
    "foto_de_evento": {
        "rotulo": "Foto de evento",
        "prompt": "a photo of people at a public event, a ceremony, a crowd",
        "descricao": "Uma foto de pessoas num evento publico.",
    },
    "retrato": {
        "rotulo": "Retrato",
        "prompt": "a portrait photo of a person, selfie, headshot",
        "descricao": "Um retrato (foto de rosto) de uma pessoa.",
    },
    "print_de_noticia": {
        "rotulo": "Print de noticia",
        "prompt": "a screenshot of a news website, a news article page",
        "descricao": "Uma captura de tela de uma pagina de noticia.",
    },
    "print_de_conversa": {
        "rotulo": "Print de conversa",
        "prompt": "a screenshot of a chat conversation, whatsapp messages, comments",
        "descricao": "Uma captura de tela de conversa (chat/comentarios).",
    },
    "meme": {
        "rotulo": "Meme",
        "prompt": "a meme picture with impact text, a funny reaction image",
        "descricao": "Uma imagem de meme.",
    },
    "grafico": {
        "rotulo": "Grafico ou infografico",
        "prompt": "an infographic, a chart, a statistic graph, a data table image",
        "descricao": "Um grafico ou infografico com dados.",
    },
    "documento": {
        "rotulo": "Documento",
        "prompt": "a scanned document, an official form, a scanned letter",
        "descricao": "Um documento digitalizado (oficio, formulario).",
    },
    "capa_de_video": {
        "rotulo": "Capa de video",
        "prompt": "a video thumbnail, a youtube video cover",
        "descricao": "A capa (thumb) de um video.",
    },
    "material_de_campanha": {
        "rotulo": "Material de campanha",
        "prompt": "a political campaign material, a party flag, an election poster",
        "descricao": "Material de campanha (material partidario, cartaz eleitoral).",
    },
    "outro": {
        "rotulo": "Outro",
        "prompt": "an unrelated photo",
        "descricao": "Uma imagem sem categoria clara.",
    },
}


# --------------------------------------------------------------------------
# I0 — download seguro
# --------------------------------------------------------------------------
class DownloadRecusado(RuntimeError):
    """O download foi recusado pela guarda de seguranca."""


def _ip_publico(host: str) -> bool:
    """True se o host resolve para IP publico (guarda anti-SSRF)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:  # noqa: BLE001
        return False
    for info in infos:
        endereco = info[4][0]
        try:
            ip = ipaddress.ip_address(endereco)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def url_segura(url: str) -> bool:
    """Aceita apenas http(s) apontando para IP publico."""
    if not url:
        return False
    try:
        partes = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if partes.scheme not in ("http", "https"):
        return False
    host = (partes.hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "0.0.0.0", "::1"}:
        return False
    try:
        if ipaddress.ip_address(host).is_loopback:
            return False
    except ValueError:
        pass
    return _ip_publico(host)


def baixar(url: str, timeout: float = TIMEOUT_DOWNLOAD) -> bytes:
    """Baixa a imagem respeitando tamanho, tipo e endereco publico."""
    if not url_segura(url):
        raise DownloadRecusado(f"URL nao segura (privada/invalida): {url}")
    import requests

    resp = requests.get(
        url,
        timeout=timeout,
        stream=True,
        headers={"User-Agent": "CerraClippingBot/1.0 (+https://github.com/renato0503)"},
    )
    resp.raise_for_status()
    tipo = (resp.headers.get("Content-Type") or "").lower()
    if not tipo.startswith("image/"):
        raise DownloadRecusado(f"Content-Type nao e imagem: {tipo or 'desconhecido'}")
    dados = bytearray()
    for bloco in resp.iter_content(65536):
        dados.extend(bloco)
        if len(dados) > TAMANHO_MAXIMO:
            raise DownloadRecusado("Arquivo maior que 8 MB")
    if not dados:
        raise DownloadRecusado("Arquivo vazio")
    return bytes(dados)


# --------------------------------------------------------------------------
# I0 — WebP, pHash e base64
# --------------------------------------------------------------------------
@dataclass
class ImagemProcessada:
    """Resultado do processamento local de uma imagem."""

    phash: str = ""
    sha256: str = ""
    largura: int = 0
    altura: int = 0
    webp_640: str = ""   # caminho do WebP 640 px
    webp_160: str = ""   # caminho do WebP 160 px
    base64_160: str = ""  # miniatura 160 px em base64 (D12: sem Blaze)
    exif_removido: bool = False
    motivo: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def processar_imagem(
    dados: bytes,
    pasta: Path | None = None,
    nome: str = "",
) -> ImagemProcessada:
    """Valida a imagem, remove EXIF, gera WebP 640/160 e calcula pHash+sha256.

    `dados` sao os bytes crus ja baixados.
    """
    from PIL import Image

    saida = ImagemProcessada()
    try:
        with Image.open(io.BytesIO(dados)) as img:
            img.verify()
    except Exception as exc:  # noqa: BLE001
        saida.motivo = f"imagem invalida: {str(exc)[:80]}"
        return saida

    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except Exception as exc:  # noqa: BLE001
        saida.motivo = f"imagem invalida: {str(exc)[:80]}"
        return saida

    saida.exif_removido = bool(getattr(img, "_getexif", lambda: None)())
    # Recria sem EXIF/GPS (reabre a partir dos pixels).
    limpo = Image.new(img.mode if img.mode in ("RGB", "L") else "RGB", img.size)
    limpo.paste(img.convert("RGB") if limpo.mode == "RGB" else img.convert("L"))
    saida.largura, saida.altura = limpo.size

    import imagehash

    saida.phash = str(imagehash.phash(limpo))
    saida.sha256 = hashlib.sha256(dados).hexdigest()

    if pasta is not None:
        pasta.mkdir(parents=True, exist_ok=True)
        base = nome or saida.phash
        w640 = _redimensionar(limpo, LARGURA_640)
        w160 = _redimensionar(limpo, LARGURA_160)
        destino640 = pasta / f"{base}_640.webp"
        destino160 = pasta / f"{base}_160.webp"
        w640.save(destino640, "WEBP", quality=72, method=4)
        w160.save(destino160, "WEBP", quality=70, method=4)
        saida.webp_640 = str(destino640)
        saida.webp_160 = str(destino160)
        buffer = io.BytesIO()
        w160.save(buffer, "WEBP", quality=60, method=4)
        saida.base64_160 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return saida


def _redimensionar(img, largura: int):
    from PIL import Image

    alvo = img.copy()
    alvo.thumbnail((largura, largura * 4), Image.LANCZOS)
    if alvo.mode not in ("RGB", "L"):
        alvo = alvo.convert("RGB")
    return alvo


def distancia_phash(a: str, b: str) -> int:
    """Distancia de Hamming entre dois pHash (0 = mesma imagem)."""
    if not a or not b or len(a) != len(b):
        return 64
    return sum(1 for x, y in zip(a, b) if x != y)


def mesma_imagem(a: str, b: str, limiar: int = 6) -> bool:
    """Duas imagens sao a mesma se a distancia de Hamming <= limiar."""
    return distancia_phash(a, b) <= limiar


# --------------------------------------------------------------------------
# I1 — OCR
# --------------------------------------------------------------------------
def ocr(dados: bytes) -> dict:
    """Le o texto da imagem com RapidOCR (ONNX, CPU).

    Devolve {"texto", "caixas": [{"texto","x0","y0","x1","y1","conf"}], "conf",
    "modelo", "motivo"}.
    """
    saida = {"texto": "", "caixas": [], "conf": 0.0, "modelo": "rapidocr", "motivo": ""}
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"rapidocr indisponivel: {str(exc)[:80]}"
        return saida
    try:
        motor = RapidOCR()
        resultado, _ = motor(dados)
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"ocr falhou: {str(exc)[:80]}"
        return saida
    if not resultado:
        saida["motivo"] = "sem_texto"
        return saida

    from PIL import Image

    with Image.open(io.BytesIO(dados)) as img:
        largura, altura = img.size
    largura = largura or 1
    altura = altura or 1

    linhas: list[str] = []
    caixas: list[dict] = []
    confianca = 0.0
    for item in resultado:
        try:
            caixa, texto, nota = item[0], item[1], item[2]
        except (IndexError, TypeError):
            continue
        xs = [ponto[0] for ponto in caixa]
        ys = [ponto[1] for ponto in caixa]
        linhas.append(str(texto))
        caixas.append(
            {
                "texto": str(texto),
                "x0": round(min(xs) / largura, 4),
                "y0": round(min(ys) / altura, 4),
                "x1": round(max(xs) / largura, 4),
                "y1": round(max(ys) / altura, 4),
                "conf": round(float(nota or 0), 3),
            }
        )
        confianca = max(confianca, float(nota or 0))
    saida["texto"] = " ".join(linhas)
    saida["caixas"] = caixas
    saida["conf"] = round(confianca, 3)
    return saida


# --------------------------------------------------------------------------
# I2 — tipo de peca (CLIP zero-shot)
# --------------------------------------------------------------------------
def classificar_tipo(dados: bytes) -> dict:
    """Classifica o tipo de peca com open_clip (zero-shot).

    Devolve {"tipo_peca", "tipo_conf", "rotulo", "descricao", "modelo", "motivo"}.
    """
    saida = {
        "tipo_peca": "outro",
        "tipo_conf": 0.0,
        "rotulo": TIPOS_PECA["outro"]["rotulo"],
        "descricao": TIPOS_PECA["outro"]["descricao"],
        "modelo": "open_clip",
        "motivo": "",
    }
    try:
        import open_clip
        import torch
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"open_clip indisponivel: {str(exc)[:80]}"
        return saida
    try:
        modelo, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        with Image.open(io.BytesIO(dados)) as img:
            tensor = preprocess(img.convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            imagem = modelo.encode_image(tensor)
            imagem = imagem / imagem.norm(dim=-1, keepdim=True)
            prompts = [v["prompt"] for v in TIPOS_PECA.values()]
            tokens = tokenizer(prompts)
            texto = modelo.encode_text(tokens)
            texto = texto / texto.norm(dim=-1, keepdim=True)
            similaridade = (100.0 * imagem @ texto.T).softmax(dim=-1)[0]
        indice = int(similaridade.argmax().item())
        chaves = list(TIPOS_PECA.keys())
        tipo = chaves[indice]
        saida.update(
            {
                "tipo_peca": tipo,
                "tipo_conf": round(float(similaridade[indice].item()), 4),
                "rotulo": TIPOS_PECA[tipo]["rotulo"],
                "descricao": TIPOS_PECA[tipo]["descricao"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"classificacao falhou: {str(exc)[:80]}"
    return saida


# --------------------------------------------------------------------------
# I3 — VLM local (Ollama, saida JSON)
# --------------------------------------------------------------------------
VLM_PROMPT = """Você analisa uma imagem de post/notícia política.
Responda APENAS com JSON, sem texto em volta, neste formato:
{
  "descricao": "uma frase describing a imagem em português",
  "n_pessoas": 0,
  "simbolos": ["brasão", "bandeira", "logo de partido", "número de urna", "logo de órgão"],
  "pedido_de_voto": false,
  "tom": "positivo|negativo|neutro|ironia",
  "tema": "saúde|transporte|obras|educação|segurança|meio ambiente|cultura|política|outro",
  "texto_confere_ocr": false
}
Regras: não invente; se não souber, use null/[]; não identifique pessoas por nome."""

VLM_SCHEMA = {
    "descricao": str,
    "n_pessoas": int,
    "simbolos": list,
    "pedido_de_voto": bool,
    "tom": str,
    "tema": str,
    "texto_confere_ocr": bool,
}


def descrever_com_vlm(
    imagem_base64: str,
    modelo: str = "qwen2.5vl:7b",
    url_ollama: str = "http://127.0.0.1:11434",
    timeout: float = 120.0,
) -> dict:
    """Chama o VLM local e devolve o JSON validado.

    Devolve {"vlm": {...}, "modelo", "versao", "motivo"}.
    """
    saida = {"vlm": {}, "modelo": modelo, "versao": "1.0", "motivo": ""}
    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"requests ausente: {exc}"
        return saida
    payload = {
        "model": modelo,
        "prompt": VLM_PROMPT,
        "images": [imagem_base64],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_ctx": 4096},
    }
    try:
        resp = requests.post(f"{url_ollama.rstrip('/')}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
        bruto = resp.json().get("response", "")
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"ollama indisponivel: {str(exc)[:100]}"
        return saida

    import json

    try:
        dados = json.loads(bruto)
    except Exception:  # noqa: BLE001
        saida["motivo"] = "resposta do modelo nao e JSON"
        return saida
    saida["vlm"] = _validar_vlm(dados)
    return saida


def _validar_vlm(dados: dict) -> dict:
    """Garante que o JSON do modelo tem os campos do schema."""
    saida = {
        "descricao": str(dados.get("descricao") or "")[:280],
        "n_pessoas": int(dados.get("n_pessoas") or 0),
        "simbolos": [str(s) for s in (dados.get("simbolos") or [])][:8],
        "pedido_de_voto": bool(dados.get("pedido_de_voto")),
        "tom": str(dados.get("tom") or "neutro"),
        "tema": str(dados.get("tema") or "outro"),
        "texto_confere_ocr": bool(dados.get("texto_confere_ocr")),
    }
    return saida


# --------------------------------------------------------------------------
# I4 — reconhecimento facial
# --------------------------------------------------------------------------
def detectar_rostos(dados: bytes) -> list[dict]:
    """Detecta rostos com YuNet (OpenCV).

    Devolve [{"caixa": [x0,y0,x1,y1], "conf": float}] em pixels da imagem.
    """
    try:
        import cv2
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        logger.info("OpenCV ausente (%s); sem deteccao de rosto.", exc)
        return []
    try:
        detector = cv2.FaceDetectorYN_create(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml", "", (320, 320), 0.6
        )
    except Exception:
        detector = None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(dados)) as img:
            arr = np.array(img.convert("RGB"))[:, :, ::-1].copy()
        altura, largura = arr.shape[:2]
        if detector is None:
            cinza = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            rostos = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            ).detectMultiScale(cinza, 1.2, 5)
            return [
                {"caixa": [int(x), int(y), int(x + w), int(y + h)], "conf": 1.0}
                for x, y, w, h in rostos
            ]
        detector.setInputSize((largura, altura))
        _, _, rostos = detector.detect(arr)
        saida = []
        for x, y, w, h in rostos:
            saida.append({"caixa": [int(x), int(y), int(x + w), int(y + h)], "conf": 1.0})
        return saida
    except Exception as exc:  # noqa: BLE001
        logger.info("Deteccao de rosto falhou: %s", exc)
        return []


def comparar_com_agentes(
    dados: bytes,
    galeria: dict[str, list[bytes]],
    limiar: float = 0.6,
) -> dict:
    """Compara os rostos detectados com a galeria de cada agente.

    `galeria`: {agente_id: [bytes de imagem de referencia]}.
    Devolve {"agente_presente": bool, "agente_id": str, "conf": float,
    "n_rostos": int, "modelo": str}.
    """
    saida = {
        "agente_presente": False,
        "agente_id": "",
        "conf": 0.0,
        "n_rostos": 0,
        "modelo": "nao_disponivel",
    }
    rostos = detectar_rostos(dados)
    saida["n_rostos"] = len(rostos)
    if not rostos:
        return saida
    try:
        import face_recognition
    except Exception:  # noqa: BLE001
        saida["motivo"] = "face_recognition ausente"
        return saida
    saida["modelo"] = "face_recognition"
    try:
        import numpy as np
        from PIL import Image

        embeddings = []
        for x, y, w, h in rostos:
            with Image.open(io.BytesIO(dados)) as img:
                recorte = img.convert("RGB").crop((x, y, x + w, y + h))
            vetor = face_recognition.face_encodings(np.array(recorte))
            if vetor:
                embeddings.append(vetor[0])
        for agente_id, referencias in (galeria or {}).items():
            for referencia in referencias or []:
                with Image.open(io.BytesIO(referencia)) as img:
                    ref = face_recognition.face_encodings(np.array(img.convert("RGB")))
                if not ref:
                    continue
                for vetor in embeddings:
                    distancia = face_recognition.face_distance([ref[0]], vetor)[0]
                    confianca = max(0.0, 1.0 - float(distancia))
                    if confianca >= limiar and confianca > saida["conf"]:
                        saida.update(
                            {"agente_presente": True, "agente_id": agente_id, "conf": round(confianca, 3)}
                        )
    except Exception as exc:  # noqa: BLE001
        saida["motivo"] = f"comparacao falhou: {str(exc)[:80]}"
    return saida


# --------------------------------------------------------------------------
# I5 — C2PA e reuso
# --------------------------------------------------------------------------
def ler_c2pa(dados: bytes) -> dict:
    """Le a credencial de conteudo (C2PA), se houver.

    Devolve {"presente": bool, "editorial": bool, "gerado_ia": bool, "detalhe": str}.
    """
    saida = {"presente": False, "editorial": False, "gerado_ia": False, "detalhe": ""}
    try:
        from c2pa import Reader
    except Exception as exc:  # noqa: BLE001
        saida["detalhe"] = f"c2pa nao instalado: {str(exc)[:60]}"
        return saida
    try:
        leitor = Reader.from_bytes(dados)
        manifesto = leitor.manifest_json()
        saida["presente"] = bool(manifesto)
        texto = str(manifesto).lower()
        saida["editorial"] = "editorial" in texto
        saida["gerado_ia"] = "ai" in texto and ("trained" in texto or "generated" in texto)
    except Exception as exc:  # noqa: BLE001
        saida["detalhe"] = f"c2pa falhou: {str(exc)[:60]}"
    return saida


def registrar_reuso(
    phash: str,
    primeira_vez: str,
    post: dict,
) -> dict:
    """Atualiza o contador de reuso de uma imagem (I5.b).

    `primeira_vez`: ISO datetime da primeira aparição.
    Devolve {"primeira_vez", "n_posts", "redes"} com a contagem atualizada.
    """
    agora = datetime.now(timezone.utc)
    try:
        primeira = datetime.fromisoformat(primeira_vez)
    except (TypeError, ValueError):
        primeira = agora
    redes = set()
    return {
        "primeira_vez": primeira.isoformat(),
        "n_posts": 1,
        "redes": sorted(redes | {post.get("rede", "")} - {""}),
        "dias_de_idade": (agora - primeira).days,
    }


def imagem_reciclada(primeira_vez: str, dias_limite: int = 30) -> bool:
    """True se a imagem ja appeared ha mais de `dias_limite` (K-74)."""
    try:
        primeira = datetime.fromisoformat(primeira_vez)
    except (TypeError, ValueError):
        return False
    agora = datetime.now(timezone.utc)
    if primeira.tzinfo is None:
        primeira = primeira.replace(tzinfo=timezone.utc)
    return (agora - primeira).days > dias_limite
