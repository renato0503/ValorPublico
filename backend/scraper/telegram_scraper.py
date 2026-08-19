from core.logger import get_logger
from scraper.base import BaseScraper
from scraper.models import TIPO_POSTAGEM, PLATAFORMA_TELEGRAM, RawItem

logger = get_logger(__name__)


class TelegramScraper(BaseScraper):
    """Monitora grupos/canais abertos do Telegram via Telethon (MTProto).

    Usa apenas a biblioteca Telethon (autenticada) — nunca clones do Pyrogram,
    alvo da "Operacao Navy Ghost" (backdoor em dependencias). Requer:
      api_id, api_hash, session_file e a lista de canais publicos a monitorar.
    """

    plataforma = PLATAFORMA_TELEGRAM

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.api_id = cfg.get("api_id", 0)
        self.api_hash = cfg.get("api_hash", "")
        self.session_file = cfg.get("session_file", "")
        self.canais: list[str] = cfg.get("canais", [])
        self.limite_por_canal = int(cfg.get("limite_por_canal", 50))

    def _cliente(self):
        from telethon import TelegramClient

        if not self.api_id or not self.api_hash:
            raise ValueError("Telegram: api_id/api_hash ausentes no .env.")
        client = TelegramClient(self.session_file, self.api_id, self.api_hash)
        client.start()
        return client

    def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        client = self._cliente()
        termos = [t.lower() for t in agente.get("termos_de_busca", [])]
        itens: list[RawItem] = []
        try:
            for canal in self.canais:
                try:
                    entidade = client.get_entity(canal)
                    for msg in client.iter_messages(
                        entidade, limit=self.limite_por_canal
                    ):
                        texto = (msg.message or "").strip()
                        if not texto:
                            continue
                        if not any(t in texto.lower() for t in termos):
                            continue
                        itens.append(
                            RawItem(
                                agente_id=agente["id"],
                                id_externo=str(msg.id),
                                plataforma=self.plataforma,
                                tipo=TIPO_POSTAGEM,
                                texto_limpo=texto,
                                data_publicacao=msg.date,
                                autor=canal,
                                url=f"https://t.me/{canal}/{msg.id}",
                                alcance=int(getattr(msg, "views", 0) or 0),
                                metadados={"canal": canal},
                            )
                        )
                    self._sleep()
                except Exception as e:  # noqa: BLE001
                    logger.warning("Telegram: falha no canal '%s' do agente %s: %s", canal, agente["id"], e)
        finally:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        logger.info("Telegram: %d itens para %s", len(itens), agente["id"])
        return itens