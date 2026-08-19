import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SEED_FILE = DATA_DIR / "seeds" / "agentes_publicos.json"

FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")

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

# Liga/desliga cada scraper (valor "1" habilita)
HABILITAR_TWITTER = os.getenv("HABILITAR_TWITTER", "1") == "1"
HABILITAR_INSTAGRAM = os.getenv("HABILITAR_INSTAGRAM", "1") == "1"
HABILITAR_FACEBOOK = os.getenv("HABILITAR_FACEBOOK", "1") == "1"
HABILITAR_WEB = os.getenv("HABILITAR_WEB", "1") == "1"

# Nomes das colecoes Firestore
COLLECTION_AGENTES = "agentes_publicos"
SUBCOLLECTION_CLIPPINGS = "clippings"