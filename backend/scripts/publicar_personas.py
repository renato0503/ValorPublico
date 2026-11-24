"""Publica os perfis das 12 personas do Governo no Firestore.

Le `simulacao/personas/governo-mt.yaml` e grava `personas/<id>` com `orgao`,
personalidade, status e versão da RAG. O chat online só é habilitado depois
que a base RAG for exportada (`rag_version` preenchida).

Uso (a partir de `backend/`):
    python scripts/publicar_personas.py --dry-run
    python scripts/publicar_personas.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

RAIZ = Path(__file__).resolve().parents[3]
SIMULACAO = RAIZ / "simulacao"
YAML = SIMULACAO / "personas" / "governo-mt.yaml"

STAKEHOLDER = {
    "servidor-estadual": "servidor publico",
    "professor-rede": "educacao",
    "profissional-saude": "saude",
    "produtor-rural": "agro",
    "empresario-industria": "industria",
    "comerciante-mei": "comercio",
    "trabalhador-informal": "trabalho informal",
    "jovem-estudante": "juventude",
    "mae-beneficiaria": "assistencia social",
    "seguranca-publica": "seguranca publica",
    "lideranca-comunitaria": "comunidade",
    "formador-opiniao": "imprensa",
}


def carregar_personas_yaml(caminho: Path) -> list[dict]:
    """Parser simples do YAML de personas (sem dependencia externa)."""
    pessoas: list[dict] = []
    atual: dict | None = None
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        sem = linha.strip()
        if not sem or sem.startswith("#"):
            continue
        if sem.startswith("- id:"):
            if atual:
                pessoas.append(atual)
            atual = {"id": sem.split(":", 1)[1].strip()}
            continue
        if atual is None:
            continue
        if sem.startswith(
            ("rotulo:", "peso:", "idade:", "genero:", "escolaridade:", "regiao:", "tom_base:")
        ):
            chave, valor = sem.split(":", 1)
            atual[chave.strip()] = valor.strip().strip('"')
        elif sem.startswith("interesses:"):
            bruto = sem.split(":", 1)[1].strip().strip("[]")
            atual["interesses"] = [i.strip() for i in bruto.split(",") if i.strip()]
        elif sem.startswith("personalidade:"):
            bruto = sem.split(":", 1)[1].strip().strip("[]")
            atual["personalidade"] = [i.strip() for i in bruto.split(",") if i.strip()]
        elif sem.startswith("valores:"):
            bruto = sem.split(":", 1)[1].strip().strip("[]")
            atual["valores"] = [i.strip() for i in bruto.split(",") if i.strip()]
    if atual:
        pessoas.append(atual)
    return pessoas


def documento(persona: dict) -> dict:
    return {
        "id": persona["id"],
        "orgao": "governo-mt",
        "rotulo": persona.get("rotulo", persona["id"]),
        "stakeholder": STAKEHOLDER.get(persona["id"], persona.get("tom_base", "")),
        "peso": int(persona.get("peso") or 0),
        "idade": persona.get("idade", ""),
        "genero": persona.get("genero", ""),
        "escolaridade": persona.get("escolaridade", ""),
        "regiao": persona.get("regiao", ""),
        "interesses": persona.get("interesses", []),
        "tom_base": persona.get("tom_base", "neutro"),
        "personalidade": persona.get("personalidade", []),
        "valores": persona.get("valores", []),
        "status": "perfil_publicado",
        "rag_version": "",
        "fonte": "Persona sintetica (TSE/IBGE/CHD/demandas)",
        "atualizado_em": datetime.now(timezone.utc),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica as personas do Governo.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    personas = carregar_personas_yaml(YAML)
    if not personas:
        logger.error("Nenhuma persona encontrada em %s", YAML)
        return 1
    docs = [(p["id"], documento(p)) for p in personas]
    logger.info("Personas carregadas: %d", len(docs))
    for pid, doc in docs:
        logger.info("  %-24s peso=%s tom=%s", pid, doc["peso"], doc["tom_base"])

    if args.dry_run:
        print("(dry-run: nada foi gravado)")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    lote = db.batch()
    for pid, doc in docs:
        lote.set(db.collection("personas").document(pid), doc, merge=True)
    lote.commit()
    logger.info("Gravadas %d personas em personas/* (orgao=governo-mt).", len(docs))
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "publicar_personas"))
