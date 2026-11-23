"""Gera a sessao autenticada do Telethon (primeiro login) e testa os canais.

Pre-requisitos no .env:
    TELEGRAM_API_ID, TELEGRAM_API_HASH   (criados em https://my.telegram.org)
    TELEGRAM_PHONE                       (ex.: 5567993515206)
    TELEGRAM_CANAIS                      (opcional p/ teste de entidades)

O codigo de verificacao chega por SMS no seu celular e a senha (2FA) e pedida
se a conta tiver. A sessao e salva em `TELEGRAM_SESSION_FILE` e reutilizada
automaticamente pelo scraper nas proximas execucoes.

Uso: python scripts/login_telegram.py [--testar-canais]
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Primeiro login do Telegram (Telethon).")
    parser.add_argument("--testar-canais", action="store_true",
                        help="Lista os canais configurados e confirma o acesso.")
    args = parser.parse_args()

    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        logger.error(
            "Defina TELEGRAM_API_ID e TELEGRAM_API_HASH no .env "
            "(crie em https://my.telegram.org)."
        )
        sys.exit(1)
    if not settings.TELEGRAM_PHONE:
        logger.error("Defina TELEGRAM_PHONE no .env (ex.: 5567993515206).")
        sys.exit(1)
    if not settings.TELEGRAM_SESSION_FILE:
        logger.error("Defina TELEGRAM_SESSION_FILE no .env (caminho do arquivo de sessao).")
        sys.exit(1)

    from telethon import TelegramClient

    caminho = Path(settings.TELEGRAM_SESSION_FILE)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(
        str(caminho),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
    )
    print("=" * 60)
    print("Login do Telegram")
    print(f"  numero: {settings.TELEGRAM_PHONE}")
    print(f"  sessao: {caminho}")
    print("  envie o codigo SMS quando solicitado (e a senha 2FA, se houver).")
    print("=" * 60)
    client.start(
        phone=settings.TELEGRAM_PHONE,
        code_callback=lambda: input("Codigo SMS: ").strip(),
        password=lambda: input("Senha 2FA (ou Enter se nao tiver): ").strip() or None,
    )
    me = client.get_me()
    print(f"Conectado como: {me.first_name} @{me.username} (id {me.id})")

    if args.testar_canais and settings.TELEGRAM_CANAIS:
        print("\nVerificando canais:")
        for canal in settings.TELEGRAM_CANAIS:
            try:
                entidade = client.get_entity(canal)
                print(f"  OK  {canal} -> {getattr(entidade, 'title', entidade.id)}")
            except Exception as e:  # noqa: BLE001
                print(f"  ERRO {canal} -> {e}")
    print("\nSessao salva. Pronto para o scraper.")
    client.disconnect()


if __name__ == "__main__":
    main()