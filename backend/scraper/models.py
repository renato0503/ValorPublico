from dataclasses import dataclass, field
from datetime import datetime, timezone

# Plataformas monitoradas
PLATAFORMA_TWITTER = "Twitter"
PLATAFORMA_INSTAGRAM = "Instagram"
PLATAFORMA_FACEBOOK = "Facebook"
PLATAFORMA_WEB = "Web"
PLATAFORMA_YOUTUBE = "YouTube"
PLATAFORMA_TELEGRAM = "Telegram"

# Tipos de clipping
TIPO_POSTAGEM = "Postagem"
TIPO_COMENTARIO = "Comentario"
TIPO_NOTICIA = "Noticia"

# Sentimentos possiveis
SENTIMENTO_POSITIVO = "positivo"
SENTIMENTO_NEGATIVO = "negativo"
SENTIMENTO_NEUTRO = "neutro"


@dataclass
class RawItem:
    """Registro bruto normalizado coletado por qualquer scraper."""

    agente_id: str
    id_externo: str
    plataforma: str
    tipo: str
    texto_limpo: str
    data_publicacao: datetime | None
    autor: str = ""
    url: str = ""
    alcance: int = 0
    metadados: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agente_id": self.agente_id,
            "id_externo": self.id_externo,
            "plataforma": self.plataforma,
            "tipo": self.tipo,
            "texto_limpo": self.texto_limpo,
            "data_publicacao": self.data_publicacao,
            "autor": self.autor,
            "url": self.url,
            "alcance": self.alcance,
            "metadados": self.metadados,
        }


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)