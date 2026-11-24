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
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "assessorpublico").strip()

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
# O coletor antigo (cookies + login) saiu do codigo (plano 19 N-9). O novo
# `facebook_publico_scraper.py` nao usa cookie de terceiro nem login alheio;
# as opcoes abaixo ficam apenas para compatibilidade de .env antigo.
FACEBOOK_USAR_COOKIES = False

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
YOUTUBE_COLETAR_COMENTARIOS = os.getenv("YOUTUBE_COLETAR_COMENTARIOS", "1") == "1"

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

# ---------------------------------------------------------------------------
# Redes sociais via buscador (sem login). Consulta o buscador com site: por
# rede e guarda o que a pagina de resultados ja exibe publicamente (titulo,
# snippet e trecho de comentario).
# Motores, em ordem de preferencia:
#   SearXNG (container proprio no Actions; sem chave, sem custo) > ddgs (reserva)
# O Google CSE foi encerrado para novos clientes e descontinua em 01/01/2027;
# Serper/SerpAPI sao pagos e ficaram fora (regra do dono: tudo gratuito).
# ---------------------------------------------------------------------------
HABILITAR_BUSCA_SOCIAL = os.getenv("HABILITAR_BUSCA_SOCIAL", "1") == "1"
BUSCA_SOCIAL_MAX_CONSULTAS = int(os.getenv("BUSCA_SOCIAL_MAX_CONSULTAS", "120"))
BUSCA_SOCIAL_MAX_RESULTADOS = int(os.getenv("BUSCA_SOCIAL_MAX_RESULTADOS", "10"))
BUSCA_SOCIAL_RODIZIO = os.getenv("BUSCA_SOCIAL_RODIZIO", "1") == "1"
BUSCA_SOCIAL_REGIAO = os.getenv("BUSCA_SOCIAL_REGIAO", "br-pt")
# SearXNG: URL do container (http://localhost:8080 no Actions). Vazio = usa ddgs.
SEARXNG_URL = os.getenv("SEARXNG_URL", "").strip()
SEARXNG_MOTORES = tuple(
    m.strip()
    for m in os.getenv("SEARXNG_MOTORES", "google,bing,brave,duckduckgo,startpage").split(",")
    if m.strip()
)
SEARXNG_TIMEOUT = float(os.getenv("SEARXNG_TIMEOUT", "20"))
# Comentarios publicos do YouTube (yt-dlp), por video.
YOUTUBE_MAX_COMENTARIOS = int(os.getenv("YOUTUBE_MAX_COMENTARIOS", "15"))

# ---------------------------------------------------------------------------
# Agentes de navegador (plano 19). Flags e ritmo.
# NAVEGADOR_STEALTH: ligado nos DOIS apps (decisao do dono, 24/11/2026).
# NAVEGADOR_CONTA_PROPRIA: automatizar pelo navegador a conta logada do
#   proprio agente (liberado pelo dono, 24/11/2026). A API oficial (06) segue
#   sendo o caminho preferencial.
# ---------------------------------------------------------------------------
NAVEGADOR_STEALTH = os.getenv("NAVEGADOR_STEALTH", "1") == "1"
NAVEGADOR_CONTA_PROPRIA = os.getenv("NAVEGADOR_CONTA_PROPRIA", "1") == "1"
NAVEGADOR_HEADLESS = os.getenv("NAVEGADOR_HEADLESS", "1") == "1"
NAVEGADOR_TIMEOUT_MS = int(os.getenv("NAVEGADOR_TIMEOUT_MS", "30000"))
# Limite de paginas por agente/dia (salvaguarda 19 §3.1.3).
NAVEGADOR_MAX_PAGINAS_AGENTE_DIA = int(os.getenv("NAVEGADOR_MAX_PAGINAS_AGENTE_DIA", "30"))
# Previa publica (N2): quantos links de redes abrir por agente/dia.
NAVEGADOR_MAX_PREVIAS_AGENTE_DIA = int(os.getenv("NAVEGADOR_MAX_PREVIAS_AGENTE_DIA", "10"))
# Pasta onde ficam os prints de evidencia (N3/N4).
NAVEGADOR_PASTA_EVIDENCIA = os.getenv(
    "NAVEGADOR_PASTA_EVIDENCIA", str(DATA_DIR / "evidencias")
)

# ---------------------------------------------------------------------------
# Tendencias (plano 07) e projecao (K-33).
# ---------------------------------------------------------------------------
TENDENCIAS_ATUALIZAR = os.getenv("TENDENCIAS_ATUALIZAR", "1") == "1"
TENDENCIAS_GEO = os.getenv("TENDENCIAS_GEO", "BR-MT")
TENDENCIAS_MAX_ITENS = int(os.getenv("TENDENCIAS_MAX_ITENS", "20"))
# YouTube Data API v3 (chave gratuita) — usada para "em alta" e comentarios.
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
# Meta Ad Library (token com ads_read). Vazio = anuncios indisponiveis.
META_AD_LIBRARY_TOKEN = os.getenv("META_AD_LIBRARY_TOKEN", "")
# Indice de crise (K-28): z-score minimo e minimo de itens.
CRISE_Z_LIMITE = float(os.getenv("CRISE_Z_LIMITE", "3"))
CRISE_MINIMO_ITENS = int(os.getenv("CRISE_MINIMO_ITENS", "5"))

# ---------------------------------------------------------------------------
# Imagens dos posts (plano 18).
# ---------------------------------------------------------------------------
IMAGENS_HABILITAR = os.getenv("IMAGENS_HABILITAR", "1") == "1"
IMAGENS_PASTA = os.getenv("IMAGENS_PASTA", str(DATA_DIR / "imagens"))
# Onde guardar a miniatura (D12): "base64" (Spark, sem Blaze) ou "storage".
IMAGENS_MINIATURA = os.getenv("IMAGENS_MINIATURA", "base64")
IMAGENS_MAX_POR_AGENTE = int(os.getenv("IMAGENS_MAX_POR_AGENTE", "24"))
IMAGENS_RETENCAO_DIAS = int(os.getenv("IMAGENS_RETENCAO_DIAS", "90"))
# VLM local (I3): modelo do Ollama usado na descricao das imagens.
IMAGENS_VLM_MODELO = os.getenv("IMAGENS_VLM_MODELO", "qwen2.5vl:7b")
IMAGENS_VLM_URL = os.getenv("IMAGENS_VLM_URL", "http://127.0.0.1:11434")
IMAGENS_OCR_HABILITAR = os.getenv("IMAGENS_OCR_HABILITAR", "1") == "1"
IMAGENS_CLIP_HABILITAR = os.getenv("IMAGENS_CLIP_HABILITAR", "1") == "1"
# Reconhecimento facial (I4): galerias de referencia por agente.
IMAGENS_RECONHECIMENTO_HABILITAR = os.getenv("IMAGENS_RECONHECIMENTO_HABILITAR", "0") == "1"


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

# IA local (Ollama) para o discurso e os textos dos graficos (plano 09/10).
# Roda na maquina do dono (RTX 4060, 8 GB) — sem API paga.
IA_LOCAL_URL = os.getenv("IA_LOCAL_URL", "http://127.0.0.1:11434")
IA_LOCAL_MODELO = os.getenv("IA_LOCAL_MODELO", "qwen3:8b")

# DeepSeek (discurso do governador e chat das personas). Chave só no .env/segredo.
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT", "180"))

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
APP_NOME = os.getenv("APP_NOME", "Assessor Público")
