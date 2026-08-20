# ValorPúblico — BI & Monitoramento de Mídia Política

Plataforma de **Business Intelligence + Web Scraping/Clipping** que consolida a
presença midiática e digital de **50 vereadores** de Cuiabá e Várzea Grande (MT),
convertendo menções, alcance e valoração espontânea da mídia em inteligência de
imagem e reputação política.

**Produção:** https://valorpublico.web.app

---

## Funcionalidades

- **Monitoramento multi-plataforma:** Web (Google News RSS + Trafilatura), **YouTube
  (ativo, com transcrição das falas)**, Twitter/X, Instagram, Facebook, Telegram,
  **TV, Rádio (transcrição de falas) e Impresso**.
- **Share de mídia destrincado:** a origem Web é classificada em Portal, Rádio, TV,
  Jornal Impresso, Governo e Redes (`processing/classificador_midia.py`).
- **Pipeline NLP:** limpeza/deduplicação (pandas) + sentimento (VADER expandido com
  léxico em português).
- **Valoração financeira espontânea (R$):** CPM por plataforma + tabela de veículos.
- **Dashboard PWA em tempo real:** KPIs com tendência, **filtros de período (Hoje/7d/30d)**,
  **série temporal por sentimento (3 linhas)**, **insights principais**, **nuvem de palavras
  interativa com filtro mensal**, share de mídia destrincado, sentimento, valoração por
  plataforma e Top 10 fontes (com filtro por tipo) — Firestore `onSnapshot`. Botão **↻ Atualizar**.
- **Temas/categorias por notícia:** 16 temas (Política/Câmara, Eleições, Governo, Justiça,
  Tecnologia...) classificados por palavras-chave (`processing/temas.py`).
- **Detalhe de notícia:** modal com valoração (R$/alcance/plataforma), categorias, palavras-chave,
  conteúdo e link original.
- **Relatórios / pesquisa avançada:** filtros por período, tipo de mídia e sentimento com
  somatórios de menções, valor (R$) e espaço — com **Exportação PDF**.
- **Análise de Mídia:** abas Estatística, Qualitativa e Repercussão Negativa.
- **Análises lexicais (estilo IRAMUTEQ):** frequência, especificidade por período,
  co-ocorrência/similaridade, AFC (mapa fatorial) e CHD (classes temáticas com Ward).
- **Exportação CSV** de auditoria com todos os clippings + metadados + temas.
- **Agendamento:** GitHub Actions (cron diário) + rotina local para Windows.

## Arquitetura

```
Backend (Python 3.12)  ->  Scrapers -> Orquestrador (async/sync + agentes em paralelo)
                              -> Cleaner -> Sentimento -> Valoração
                              -> Análises lexicais (numpy/scipy/sklearn)
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
  processing/     cleaner, sentiment (VADER PT), valoracao, classificador de mídia,
                  nuvem de palavras e análises lexicais (IRAMUTEQ)
  storage/        repositório Firestore
  scripts/        seed, ingestão, métricas, export CSV, análise lexical, owner, rotina
frontend/         PWA (dashboard, service worker, manifest)
firestore.rules   Security Rules (RBAC)
```

## Como executar

### Pré-requisitos
- Python 3.12+, `firebase-admin`, `pandas`, `numpy`, `scipy`, `sklearn`,
  `httpx[http2]`, `trafilatura`, `feedparser`, `yt-dlp` (ver `backend/requirements.txt`).
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

### Auditoria e análises
```powershell
# Exporta todos os clippings para CSV (auditoria/busca)
python scripts/exportar_clippings.py

# Análises lexicais estilo IRAMUTEQ (gera data/export/lexical/)
python scripts/analise_lexical.py
python scripts/analise_lexical.py --n-classes 6   # ajusta classes da CHD
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

- `context.md` — contexto estratégico, estado atual e análises lexicais.
- `implementation.md` — plano de sprints (até Go live + melhorias contínuas).

## Segurança

- Nunca versionar `.env`, `serviceAccountKey*`, `frontend/firebase-config.js`,
  cookies/sessões/proxies (ver `.gitignore`).
- A API key web do Firebase (em `frontend/js/firebase-init.js`) é **pública por
  design** e não é um segredo.