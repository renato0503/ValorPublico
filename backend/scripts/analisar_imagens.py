"""Analisa as imagens dos clippings (plano 18, fases I0–I5).

Pipeline por imagem (chave = pHash, para analisar cada imagem **uma vez**):
  I0  baixa com seguranca (anti-SSRF, <= 8 MB, Content-Type image/*), remove
      EXIF/GPS, gera WebP 640/160 px + sha256 + pHash;
  I1  OCR (RapidOCR) -> o texto volta para o pipeline de sentimento/tema;
  I2  tipo de peca (open_clip zero-shot) + confianca;
  I3  descricao e sinais pelo VLM local (Ollama, JSON) — so na maquina do dono;
  I4  reconhecimento facial (opt-in) — rosto do agente e dos demais agents;
  I5  regras de compliance sobre o texto da imagem + reuso (pHash) + C2PA.

Grava:
  metricas_por_agente/<id>.imagens  {kpis, por_tipo, galeria[<=24], mais_circularam[<=10]}
  metricas/geral.imagens            {kpis, por_tipo}
  imagens/<phash>                  (privado: ocr, tipo_peca, vlm, reuso)

Uso (a partir de `backend/`):
    python scripts/analisar_imagens.py --agentes 5            # so alguns
    python scripts/analisar_imagens.py --limite 100            # teto do lote
    python scripts/analisar_imagens.py --sem-firestore        # so processa
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.processing.imagem import (
    classificar_tipo,
    comparar_com_agentes,
    descrever_com_vlm,
    distancia_phash,
    imagem_reciclada,
    ler_c2pa,
    ocr,
    processar_imagem,
)
from config import settings
from core.quota import main_com_cota

logger = get_logger(__name__)

TETO_GALERIA = settings.IMAGENS_MAX_POR_AGENTE
TETO_MAIS_CIRCULARAM = 10


def _coleta_imagens(db, limite_agentes: int) -> list[dict]:
    """Le os clippings com `midia` (campo do plano 18, I0)."""
    itens: list[dict] = []
    for doc in db.collection("agentes_publicos").stream():
        agente = doc.to_dict() or {}
        for clip in doc.reference.collection("clippings").stream():
            dados = clip.to_dict() or {}
            midia = dados.get("midia") or []
            if not midia:
                continue
            itens.append(
                {
                    "agente_id": doc.id,
                    "agente": agente,
                    "clipping": dados,
                    "midia": midia,
                }
            )
            if len(itens) >= limite_agentes * 20:
                break
    return itens


def _processar_item(item: dict, pasta: Path, galeria: dict, vistos: dict, use_vlm: bool) -> dict | None:
    """Processa a primeira imagem do clipping. Devolve o registro da galeria."""
    midia = item["midia"][:3]  # analisar os 3 primeiros (carrossel)
    for indice, entrada in enumerate(midia):
        url = (entrada.get("url_original") or "").strip()
        if not url:
            continue
        try:
            from cerra_nucleo.processing.imagem import baixar

            dados = baixar(url)
        except Exception as exc:  # noqa: BLE001
            logger.info("Download recusado (%s): %s", url[:80], str(exc)[:80])
            continue

        processado = processar_imagem(dados, pasta=pasta, nome="img")
        if not processado.phash:
            continue

        # Reuso: ja vimos essa imagem antes?
        primeira = vistos.get(processado.phash)
        if primeira is None:
            vistos[processado.phash] = {
                "primeira_vez": datetime.now(timezone.utc).isoformat(),
                "n_posts": 0,
                "redes": [],
                "clippings": [],
            }
        registro = vistos[processado.phash]
        registro["n_posts"] += 1
        rede = item["clipping"].get("plataforma", "")
        if rede and rede not in registro["redes"]:
            registro["redes"].append(rede)
        if len(registro["clippings"]) < 50:
            registro["clippings"].append(item["clipping"].get("id_externo", ""))

        texto_imagem = ""
        leitura_ocr: dict = {}
        if settings.IMAGENS_OCR_HABILITAR:
            leitura_ocr = ocr(dados)
            texto_imagem = leitura_ocr.get("texto", "")

        tipo = {"tipo_peca": "outro", "tipo_conf": 0.0}
        if settings.IMAGENS_CLIP_HABILITAR:
            tipo = classificar_tipo(dados)

        vlm: dict = {}
        if use_vlm:
            import base64

            vlm = descrever_com_vlm(
                base64.b64encode(dados).decode("ascii"),
                modelo=settings.IMAGENS_VLM_MODELO,
                url_ollama=settings.IMAGENS_VLM_URL,
            )

        rosto = {"agente_presente": False, "n_rostos": 0}
        if settings.IMAGENS_RECONHECIMENTO_HABILITAR:
            rosto = comparar_com_agentes(dados, galeria.get("rostos", {}))

        c2pa = ler_c2pa(dados)

        return {
            "phash": processado.phash,
            "thumb": processado.base64_160[:4000],
            "rede": item["clipping"].get("plataforma", ""),
            "data": str(item["clipping"].get("data_publicacao") or "")[:10],
            "url": item["clipping"].get("url", ""),
            "tipo": tipo.get("tipo_peca", "outro"),
            "tipo_rotulo": tipo.get("rotulo", ""),
            "resumo": (vlm.get("vlm", {}).get("descricao") or texto_imagem[:120]),
            "texto_imagem": texto_imagem[:600],
            "sentimento": item["clipping"].get("sentimento", ""),
            "agente_presente": rosto.get("agente_presente", False),
            "n_rostos": rosto.get("n_rostos", 0),
            "ocr_confianca": leitura_ocr.get("conf", 0.0),
            "reuso": {
                "primeira_vez": registro["primeira_vez"],
                "n_posts": registro["n_posts"],
                "redes": registro["redes"],
            },
            "reciclada": imagem_reciclada(registro["primeira_vez"]),
            "c2pa": c2pa,
            "vlm": vlm.get("vlm", {}),
            "_registro": registro,
            "_ocr": leitura_ocr,
        }
    return None


def _kpis(registros: list[dict]) -> dict:
    """K-70 a K-75 (plano 18 §7)."""
    total = len(registros)
    if not total:
        return {
            "k70_postos_com_imagem": 0,
            "k71_presenca_agente": 0.0,
            "k72_cards_com_texto": 0.0,
            "k73_engajamento_por_tipo": {},
            "k74_imagens_recicladas": 0,
            "k75_alertas_vindos_de_imagem": 0,
        }
    com_agente = sum(1 for r in registros if r.get("agente_presente"))
    cards = sum(1 for r in registros if r.get("tipo") == "card_com_texto")
    recicladas = sum(1 for r in registros if r.get("reciclada"))
    por_tipo: dict[str, dict] = {}
    for r in registros:
        tipo = r.get("tipo", "outro")
        item = por_tipo.setdefault(tipo, {"n": 0, "sentimentos": {}})
        item["n"] += 1
        sent = r.get("sentimento", "neutro") or "neutro"
        item["sentimentos"][sent] = item["sentimentos"].get(sent, 0) + 1
    return {
        "k70_postos_com_imagem": total,
        "k71_presenca_agente": round(com_agente / total, 3),
        "k72_cards_com_texto": round(cards / total, 3),
        "k73_engajamento_por_tipo": {
            tipo: {
                "n": item["n"],
                "sentimentos": item["sentimentos"],
            }
            for tipo, item in sorted(por_tipo.items(), key=lambda kv: -kv[1]["n"])
        },
        "k74_imagens_recicladas": recicladas,
        "k75_alertas_vindos_de_imagem": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analisa as imagens dos clippings.")
    parser.add_argument("--agentes", type=int, default=5, help="quantos agentes processar")
    parser.add_argument("--limite", type=int, default=100, help="teto de imagens no lote")
    parser.add_argument("--vlm", action="store_true", help="rodar o VLM local (maquina do dono)")
    parser.add_argument("--sem-firestore", action="store_true", help="so processa, nao grava")
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    pasta = Path(settings.IMAGENS_PASTA)
    pasta.mkdir(parents=True, exist_ok=True)

    itens = _coleta_imagens(db, args.agentes)
    logger.info("Clippings com midia: %d", len(itens))

    galeria_por_agente: dict[str, list[dict]] = {}
    vistos: dict[str, dict] = {}
    processados = 0

    for item in itens:
        if processados >= args.limite:
            break
        registro = _processar_item(item, pasta, galeria_por_agente, vistos, args.vlm)
        if not registro:
            continue
        processados += 1
        agente_id = item["agente_id"]
        galeria_por_agente.setdefault(agente_id, []).append(registro)

    logger.info("Imagens processadas: %d (pHash unicos: %d)", processados, len(vistos))

    if args.sem_firestore:
        print("Dry-run: imagens processadas (sem gravar).")
        return 0

    # Grava os agregados por agente.
    for agente_id, registros in galeria_por_agente.items():
        kpis = _kpis(registros)
        ordenados = sorted(
            registros, key=lambda r: (r.get("data") or ""), reverse=True
        )[:TETO_GALERIA]
        mais_circularam = sorted(
            vistos.values(), key=lambda v: -v.get("n_posts", 0)
        )[:TETO_MAIS_CIRCULARAM]
        db.collection("metricas_por_agente").document(agente_id).set(
            {
                "imagens": {
                    "kpis": kpis,
                    "por_tipo": kpis["k73_engajamento_por_tipo"],
                    "galeria": [
                        {k: v for k, v in r.items() if not k.startswith("_") and k != "c2pa"}
                        for r in ordenados
                    ],
                    "mais_circularam": [
                        {
                            "n_posts": v.get("n_posts", 0),
                            "redes": v.get("redes", []),
                            "primeira_vez": v.get("primeira_vez", ""),
                        }
                        for v in mais_circularam
                    ],
                    "atualizado_em": datetime.now(timezone.utc).isoformat(),
                }
            },
            merge=True,
        )
    logger.info("metricas_por_agente.imagens gravado para %d agentes.", len(galeria_por_agente))

    # Grava os agregados gerais.
    todos = [r for rs in galeria_por_agente.values() for r in rs]
    db.collection("metricas").document("geral").set(
        {"imagens": {"kpis": _kpis(todos), "atualizado_em": datetime.now(timezone.utc).isoformat()}},
        merge=True,
    )

    # Grava a analise por pHash (colecao privada `imagens`).
    for phash, registro in vistos.items():
        db.collection("imagens").document(phash).set(
            {
                "reuso": {
                    "primeira_vez": registro["primeira_vez"],
                    "n_posts": registro["n_posts"],
                    "redes": registro["redes"],
                    "clippings": registro["clippings"][:50],
                },
                "analisado_em": datetime.now(timezone.utc).isoformat(),
                "expira_em": (
                    datetime.now(timezone.utc) + timedelta(days=settings.IMAGENS_RETENCAO_DIAS)
                ).isoformat(),
            },
            merge=True,
        )
    logger.info("Colecao `imagens` atualizada (%d pHash).", len(vistos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_com_cota(main, "analisar_imagens"))
