"""Publica o relatório de recepção das personas (MiroFish/painel) no Firestore.

Le `simulacao/dados/<semana>/<escopo>/painel.json` e grava
`simulacao_semanal/<escopo>__<semana>` com o campo `orgao`, os detalhes por
persona, as métricas e o aviso legal.

Uso (a partir de `backend/`):
    python scripts/publicar_simulacao.py --semana 2026-W48 --escopo casa-governo-mt
    python scripts/publicar_simulacao.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger  # noqa: E402
from core.orgaos import POR_CASA_DOC  # noqa: E402

logger = get_logger(__name__)

RAIZ = Path(__file__).resolve().parents[3]
SIMULACAO = RAIZ / "simulacao"
AVISO = "Simulação (hipótese) — não é pesquisa. Uso interno."


def semana_atual() -> str:
    return datetime.now(timezone.utc).strftime("%G-W%V")


def orgao_do_escopo(escopo: str) -> str:
    if escopo.startswith("casa-"):
        return POR_CASA_DOC.get(escopo[len("casa-") :], "")
    if escopo.startswith("agente-"):
        if "governador" in escopo or "interino" in escopo:
            return "governo-mt"
    return ""


def montar_documento(escopo: str, semana: str, painel: dict) -> dict:
    variantes = painel.get("variantes") or []
    vencedora_id = painel.get("vencedora") or (variantes[0]["id"] if variantes else "")
    vencedora = next((v for v in variantes if v.get("id") == vencedora_id), variantes[0] if variantes else {})
    personas = vencedora.get("detalhe_personas") or []
    return {
        "orgao": orgao_do_escopo(escopo),
        "escopo": escopo,
        "semana": semana,
        "metodo": "painel_n2",
        "modelo": painel.get("modelo") or "",
        "fonte": painel.get("fonte") or "",
        "discurso_ref": f"discurso_semanal/{escopo}__{semana}",
        "personas": personas,
        "variantes": [
            {
                "id": v.get("id"),
                "adesao": v.get("adesao_media"),
                "adesao_ic90": v.get("adesao_ic"),
                "rejeicao": round(float(v.get("rejeicao_pct") or 0) / 100.0, 4),
                "polarizacao": v.get("polarizacao"),
                "frases_risco": v.get("frases_risco") or [],
                "comentarios_amostra": v.get("comentarios_amostra") or [],
            }
            for v in variantes
        ],
        "vencedora": vencedora_id,
        "polarizacao": vencedora.get("polarizacao", 0),
        "estabilidade": painel.get("estabilidade_delta", 0),
        "frases_risco": vencedora.get("frases_risco") or [],
        "gerado_em": painel.get("medido_em") or datetime.now(timezone.utc).isoformat(),
        "aviso": AVISO,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica a simulação das personas.")
    parser.add_argument("--semana", default=semana_atual())
    parser.add_argument("--escopo", default="casa-governo-mt")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    caminho = SIMULACAO / "dados" / args.semana / args.escopo / "painel.json"
    if not caminho.exists():
        logger.error("Painel nao encontrado: %s", caminho)
        return 1
    painel = json.loads(caminho.read_text(encoding="utf-8"))
    documento = montar_documento(args.escopo, args.semana, painel)
    logger.info(
        "Simulacao %s/%s: %d personas | vencedora %s | adesao %.2f",
        args.escopo,
        args.semana,
        len(documento["personas"]),
        documento["vencedora"],
        (documento["variantes"][0].get("adesao") or 0) if documento["variantes"] else 0,
    )
    if args.dry_run:
        print(json.dumps(documento, ensure_ascii=False, indent=2)[:2000])
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    db.collection("simulacao_semanal").document(
        f"{args.escopo}__{args.semana}"
    ).set(documento, merge=True)
    logger.info("Gravado simulacao_semanal/%s__%s", args.escopo, args.semana)
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "publicar_simulacao"))
