import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SEED_FILE = DATA_DIR / "seeds" / "agentes_publicos.json"

# Caminho da credencial de servico. Relativo e resolvido a partir de backend/,
# para nao quebrar se a pasta do projeto mudar de lugar.
_caminho_credencial = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
if not _caminho_credencial:
    _caminho_credencial = "serviceAccountKey.json"
_caminho_credencial = Path(_caminho_credencial)
if not _caminho_credencial.is_absolute():
    _caminho_credencial = BASE_DIR / _caminho_credencial
FIREBASE_SERVICE_ACCOUNT = str(_caminho_credencial)
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")
# Projeto Firestore esperado. A credencial precisa apontar para ele; caso
# contrario o cliente aborta (defesa em profundidade contra o achado A1).
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "valorpublico-b1e6d").strip()

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
INSTAGRAM_SESSION_FILE = os.getenv("INSTAGRAM_SESSION_FILE", "")
# instaloader ban por IP em alta cadencia: limite conservador por perfil
INSTAGRAM_MAX_POSTS_PERFIL = int(os.getenv("INSTAGRAM_MAX_POSTS_PERFIL", "20"))

FACEBOOK_COOKIES_FILE = os.getenv("FACEBOOK_COOKIES_FILE", "")
FACEBOOK_USERNAME = os.getenv("FACEBOOK_USERNAME", "")
FACEBOOK_PASSWORD = os.getenv("FACEBOOK_PASSWORD", "")
FACEBOOK_HEADLESS = os.getenv("FACEBOOK_HEADLESS", "1") == "1"
FACEBOOK_MAX_ROLAGENS = int(os.getenv("FACEBOOK_MAX_ROLAGENS", "5"))

# Contas Twitter no formato "user:pass:email;user2:pass2:email2"
TWITTER_ACCOUNTS = [
    tuple(parte.split(":"))
    for parte in os.getenv("TWITTER_ACCOUNTS", "").split(";")
    if parte.strip()
]
# Arquivo JSON {username: {auth_token, ct0, ...}} com cookies reais do navegador
TWITTER_COOKIES_FILE = os.getenv("TWITTER_COOKIES_FILE", "")

PROXY_LIST = [p.strip() for p in os.getenv("PROXY_LIST", "").split(",") if p.strip()]
SCRAPE_DELAY_MIN = float(os.getenv("SCRAPE_DELAY_MIN", "2"))
SCRAPE_DELAY_MAX = float(os.getenv("SCRAPE_DELAY_MAX", "6"))
INCLUIR_COMENTARIOS = os.getenv("INCLUIR_COMENTARIOS", "1") == "1"
LIMITE_ITENS_POR_AGENTE = int(os.getenv("LIMITE_ITENS_POR_AGENTE", "50"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
# Quantos agentes sao processados simultaneamente na ingestao
PARALELISMO_AGENTES = int(os.getenv("PARALELISMO_AGENTES", "4"))

# Liga/desliga cada scraper (valor "1" habilita)
HABILITAR_TWITTER = os.getenv("HABILITAR_TWITTER", "1") == "1"
HABILITAR_INSTAGRAM = os.getenv("HABILITAR_INSTAGRAM", "1") == "1"
HABILITAR_FACEBOOK = os.getenv("HABILITAR_FACEBOOK", "1") == "1"
HABILITAR_WEB = os.getenv("HABILITAR_WEB", "1") == "1"
HABILITAR_YOUTUBE = os.getenv("HABILITAR_YOUTUBE", "1") == "1"
HABILITAR_TELEGRAM = os.getenv("HABILITAR_TELEGRAM", "1") == "1"

# Web: enriquecer busca o corpo do artigo (lento). Desabilite para coletar
# apenas titulo+resumo do RSS (rapido).
WEB_ENRIQUECER = os.getenv("WEB_ENRIQUECER", "1") == "1"

# YouTube
YOUTUBE_COLETAR_TRANSCRICAO = os.getenv("YOUTUBE_COLETAR_TRANSCRICAO", "1") == "1"
YOUTUBE_MAX_VIDEOS = int(os.getenv("YOUTUBE_MAX_VIDEOS", "5"))

# Telegram (Telethon)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0") or "0")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION_FILE = os.getenv("TELEGRAM_SESSION_FILE", "")
# Numero (com DDI) usado no primeiro login para gerar a sessao
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_CANAIS = [
    c.strip()
    for c in os.getenv("TELEGRAM_CANAIS", "").split(",")
    if c.strip()
]
TELEGRAM_LIMITE_POR_CANAL = int(os.getenv("TELEGRAM_LIMITE_POR_CANAL", "50"))

# TV / Radio (transcricao de falas via canais de noticia no YouTube)
HABILITAR_TV = os.getenv("HABILITAR_TV", "1") == "1"
HABILITAR_RADIO = os.getenv("HABILITAR_RADIO", "1") == "1"
TV_CANAIS = [c.strip() for c in os.getenv("TV_CANAIS", "").split(",") if c.strip()]
RADIO_CANAIS = [c.strip() for c in os.getenv("RADIO_CANAIS", "").split(",") if c.strip()]
MIDIA_VIDEOS_POR_CANAL = int(os.getenv("MIDIA_VIDEOS_POR_CANAL", "10"))

# Impresso (jornais impressos com edicao digital)
HABILITAR_IMPRESSO = os.getenv("HABILITAR_IMPRESSO", "1") == "1"
IMPRESSO_SITES = [s.strip() for s in os.getenv("IMPRESSO_SITES", "").split(",") if s.strip()]

# Avaliacao IA do sentimento (alternativa ao VADER, OpenAI-compativel)
# Quando desabilitado ou sem API key, o pipeline usa VADER + lexico PT.
IA_SENTIMENTO_ENABLED = os.getenv("IA_SENTIMENTO_ENABLED", "0") == "1"
IA_SENTIMENTO_BASE_URL = os.getenv("IA_SENTIMENTO_BASE_URL", "https://api.openai.com/v1")
IA_SENTIMENTO_API_KEY = os.getenv("IA_SENTIMENTO_API_KEY", "")
IA_SENTIMENTO_MODEL = os.getenv("IA_SENTIMENTO_MODEL", "gpt-4o-mini")
IA_SENTIMENTO_MAX_ITENS = int(os.getenv("IA_SENTIMENTO_MAX_ITENS", "200"))
IA_SENTIMENTO_TAMANHO_LOTE = int(os.getenv("IA_SENTIMENTO_TAMANHO_LOTE", "20"))
IA_SENTIMENTO_TIMEOUT = int(os.getenv("IA_SENTIMENTO_TIMEOUT", "30"))
IA_SENTIMENTO_TEMPERATURA = float(os.getenv("IA_SENTIMENTO_TEMPERATURA", "0.0"))

# Release de IA (resumo executivo por escopo/periodo, OpenAI-compativel).
# Reusa a mesma API key do sentimento quando IA_RELEASE_API_KEY nao for informada.
IA_RELEASE_ENABLED = os.getenv("IA_RELEASE_ENABLED", "1") == "1"
IA_RELEASE_BASE_URL = os.getenv(
    "IA_RELEASE_BASE_URL",
    os.getenv("IA_SENTIMENTO_BASE_URL", "https://api.openai.com/v1"),
)
IA_RELEASE_API_KEY = os.getenv(
    "IA_RELEASE_API_KEY",
    os.getenv("IA_SENTIMENTO_API_KEY", ""),
)
IA_RELEASE_MODEL = os.getenv("IA_RELEASE_MODEL", "gpt-4o-mini")
IA_RELEASE_TIMEOUT = int(os.getenv("IA_RELEASE_TIMEOUT", "60"))
IA_RELEASE_TEMPERATURA = float(os.getenv("IA_RELEASE_TEMPERATURA", "0.4"))
# Maximo de trechos (clippings) enviados como contexto ao modelo por release
IA_RELEASE_MAX_TRECHOS = int(os.getenv("IA_RELEASE_MAX_TRECHOS", "15"))

# Nomes das colecoes Firestore
COLLECTION_AGENTES = "agentes_publicos"
SUBCOLLECTION_CLIPPINGS = "clippings"

# ---------------------------------------------------------------------------
# Camada DSM: radar de propaganda publica, compliance eleitoral, alertas,
# cobertura/SLA e newsletter (recursos de mercado estudados em 2026).
# ---------------------------------------------------------------------------

# Fontes oficiais/institucionais monitoradas pelo radar de propaganda publica.
# Padrao: lista curada de Cuiaba, Varzea Grande e Assembleia/Estado de MT
# (ver config/fontes_radar.py). Formato: URL1,URL2 (paginas ou feeds RSS).
from config.fontes_radar import FONTES_RADAR_PADRAO  # noqa: E402

FONTES_PROPAGANDA_PUBLICA = [
    u.strip() for u in os.getenv("FONTES_PROPAGANDA_PUBLICA", "").split(",") if u.strip()
] or list(FONTES_RADAR_PADRAO)
HABILITAR_PROPAGANDA_PUBLICA = os.getenv("HABILITAR_PROPAGANDA_PUBLICA", "1") == "1"
PROPAGANDA_PUBLICA_MAX_ITENS = int(os.getenv("PROPAGANDA_PUBLICA_MAX_ITENS", "20"))

# Veiculos considerados de alto impacto (Tier 1) - usados no SLA, alertas e
# priorizacao de escopo. Sobreponivel por env.
TIER1_VEICULOS = [
    v.strip().lower()
    for v in os.getenv("TIER1_VEICULOS", "").split(",")
    if v.strip()
]
# Lista de veiculos que o escopo se compromete a monitorar (contrato).
# Se um deles nao aparece no periodo, o painel reporta "faltando".
VEICULOS_ESPERADOS = [
    v.strip().lower()
    for v in os.getenv("VEICULOS_ESPERADOS", "").split(",")
    if v.strip()
]

# Limiar (R$) a partir do qual uma mencao direta vira alerta de alto valor.
ALERTA_VALOR_ALTO = float(os.getenv("ALERTA_VALOR_ALTO", "1500"))

# Compliance eleitoral (Lei 9.504/1997). Ano do ciclo eleitoral em referencia.
COMPLIANCE_ELEITORAL_ENABLED = os.getenv("COMPLIANCE_ELEITORAL_ENABLED", "1") == "1"
ELEICAO_ANO = os.getenv("ELEICAO_ANO", "2026")
ELEICAO_1O_TURNO = os.getenv("ELEICAO_1O_TURNO", "")
ELEICAO_2O_TURNO = os.getenv("ELEICAO_2O_TURNO", "")

# Newsletter consolidada (HTML + texto para WhatsApp).
NEWSLETTER_ENABLED = os.getenv("NEWSLETTER_ENABLED", "1") == "1"
# Webhook generico para entrega (Make/Zapier/n8n): recebe {escopo, periodo, texto, html}
NEWSLETTER_WEBHOOK = os.getenv("NEWSLETTER_WEBHOOK", "")
NEWSLETTER_MAX_ITENS = int(os.getenv("NEWSLETTER_MAX_ITENS", "15"))
NEWSLETTER_ASSINATURA = os.getenv("NEWSLETTER_ASSINATURA", "Valor Publico - Monitoramento de Midia")

# Colecoes novas (radar, alertas, cobertura, newsletters)
COLLECTION_ALERTAS = "alertas"
COLLECTION_RADARES = "radares"
COLLECTION_COBERTURA = "cobertura"
COLLECTION_NEWSLETTERS = "newsletters"

# ---------------------------------------------------------------------------
# Entrega de alertas (e-mail SMTP + webhook) e configuracoes de relatorio.
# ---------------------------------------------------------------------------
ALERTA_NIVEL_MINIMO = os.getenv("ALERTA_NIVEL_MINIMO", "alto")
ALERTA_WEBHOOK_URL = os.getenv("ALERTA_WEBHOOK_URL", "")
ALERTA_WEBHOOK_SECRET = os.getenv("ALERTA_WEBHOOK_SECRET", "")
ALERTA_DESTINATARIOS = [
    d.strip() for d in os.getenv("ALERTA_DESTINATARIOS", "").split(",") if d.strip()
]

# Envio por e-mail (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TLS = os.getenv("SMTP_TLS", "1") == "1"
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_PARA = [
    d.strip() for d in os.getenv("EMAIL_PARA", "").split(",") if d.strip()
]

# Relatorio PDF
PDF_ASSINATURA = os.getenv("PDF_ASSINATURA", "")
PDF_INCLUIR_CAMADA_DSM = os.getenv("PDF_INCLUIR_CAMADA_DSM", "1") == "1"
# Nome do produto usado em relatorios e cabecalhos
APP_NOME = os.getenv("APP_NOME", "Valor Público")
