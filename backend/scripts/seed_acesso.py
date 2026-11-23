"""Prepara o controle de acesso do painel (modo publico x acesso por agente).

Grava o documento `config_acesso/publico` com `{publico: true}` — enquanto for
`true`, o dashboard funciona em modo aberto (uso comercial/demo). Para ativar o
acesso individual:

  1. habilite o provedor "E-mail/Senha" no Firebase Authentication;
  2. crie o usuario no Authentication;
  3. crie o perfil em `usuarios/<uid>` com {papel, email, agente_id, agente_ids};
  4. rode este script com `--restrito` para gravar `{publico: false}`.

A partir dai as `firestore.rules` exigem `request.auth` e liberam cada agente
apenas para o proprio escopo (`metricas_por_agente/<id>`, `alertas/agente-<id>`,
`radares/agente-<id>`, `cobertura/agente-<id>`, `newsletters/agente-<id>`).

Uso:
    python scripts/seed_acesso.py                # modo publico
    python scripts/seed_acesso.py --restrito      # exige login
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

COLECAO = "config_acesso"
DOCUMENTO = "publico"


def main() -> None:
    restrito = "--restrito" in sys.argv
    db = init_firebase()
    db.collection(COLECAO).document(DOCUMENTO).set(
        {
            "publico": not restrito,
            "modo": "restrito" if restrito else "publico",
            "atualizado_em": datetime.now(timezone.utc),
            "observacao": (
                "publico=false exige Firebase Auth e perfis em usuarios/{uid} "
                "com agente_id/agente_ids."
            ),
        },
        merge=True,
    )
    logger.info(
        "Modo de acesso gravado: %s (publico=%s).",
        "restrito" if restrito else "publico",
        not restrito,
    )


if __name__ == "__main__":
    main()
