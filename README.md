# ValorPúblico — BI & Monitoramento de Mídia Política

Plataforma de **Business Intelligence + Web Scraping/Clipping** que consolida a
presença midiática e digital de **50 vereadores** de Cuiabá e Várzea Grande (MT),
convertendo menções, alcance e valoração espontânea da mídia em inteligência de
imagem e reputação política.

**Produção:** https://valorpublico.web.app

---

## Funcionalidades

- **Monitoramento multi-plataforma:** Web (Google News RSS + Trafilatura),
  Twitter/X, Instagram, Facebook, YouTube, Telegram, **TV, Rádio (transcrição de
  falas) e Impresso**.
- **Pipeline NLP:** limpeza/deduplicação (pandas) + sentimento (VADER expandido
  com léxico em português).
- **Valoração financeira espontânea (R$):** CPM por plataforma + tabela de
  veículos (portal/impresso).
- **Dashboard PWA em tempo real:** KPIs com tendência, série temporal, share de
  mídia, sentimento, valoração por plataforma e Top 10 fontes (Firestore
  `onSnapshot`).
- **Agendamento:** GitHub Actions (cron diário) + rotina local para Windows.

## Arquitetura

```
Backend (Python 3.12)  ->  Scrapers -> Orquestrador (async/sync paralelo)
                              -> Cleaner -> Sentimento -> Valoração
                              -> Firestore (subcoleção clippings)
Frontend (PWA/JS)      ->  Dashboard BI (tempo real via onSnapshot)
Agendamento            ->  GitHub Actions / rotina local
```

- **Banco:** Google Firebase Firestore (NoSQL) — `agentes_publicos/{id}/clippings`,
  `metricas`, `metricas_por_cidade`, `metricas_por_agente`, `tabela_midia`,
  `usuarios`, `execucoes_ingestao`.
- **Segurança:** `firestore.rules` com leitura pública do dashboard; escrita
  restrita ao backend (Admin SDK).

## Estrutura

```
backend/
  config/         settings (.env) e convenções
  core/           cliente Firebase e logging
  scraper/        scrapers + orquestrador + modelos
  processing/     cleaner (pandas) + sentimento (VADER PT) + valoração
  storage/        repositório Firestore
  scripts/        seed, ingestão, métricas, owner, rotina diária
frontend/         PWA (dashboard, service worker, manifest)
firestore.rules   Security Rules (RBAC)
```

## Como executar

### Pré-requisitos
- Python 3.12+, `firebase-admin`, `pandas`, `httpx[http2]`, `trafilatura`,
  `feedparser`, `yt-dlp`, `youtube-transcript-api` (ver `backend/requirements.txt`).
- Conta de serviço do Firebase (`FIREBASE_SERVICE_ACCOUNT` no `.env`).

### Instalação
```powershell
cd backend
pip install -r requirements.txt
Copy-Item .env.example .env   # edite com suas credenciais
```

### Pipeline
```powershell
# 1. Popular agentes (50 parlamentares)
python scripts/seed_firebase.py

# 2. Tabela de valoração (CPM + veículos)
python scripts/seed_tabela_midia.py

# 3. Ingestão (retomada: apenas agentes sem dados)
python scripts/run_ingestao.py --apenas-sem-dados

# 4. Regenerar métricas
python scripts/atualizar_metricas.py

# 5. Recriar owner (RBAC)
python scripts/criar_owner.py
```

### Agendamento
- **Nuvem:** `.github/workflows/ingestao.yml` (cron 06:30/18:30 UTC). Configure os
  secrets `FIREBASE_DATABASE_URL` e `FIREBASE_SERVICE_ACCOUNT_B64`.
- **Local:** `backend/scripts/rotina_diaria.ps1` (via Agendador de Tarefas).

### Deploy
```powershell
firebase deploy --only hosting,firestore:rules
```

## Documentação

- `context.md` — contexto estratégico e estado atual.
- `implementation.md` — plano de sprints (até Go live).

## Segurança

- Nunca versionar `.env`, `serviceAccountKey*`, `frontend/firebase-config.js`,
  cookies/sessões/proxies (ver `.gitignore`).
- A API key web do Firebase (em `frontend/js/firebase-init.js`) é **pública por
  design** e não é um segredo.