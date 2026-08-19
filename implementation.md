# ValorPúblico — Plano de Implementação (Sprints)

> Roteiro de execução da plataforma, da base até o **go live** completo.
> Atualizado em: 19/08/2026.

---

## Resumo Geral de Sprints

| Sprint | Tema | Entrega principal | Status |
|---|---|---|---|
| 0 | Setup do projeto | Repositório, estrutura, convenções, `.gitignore` | ✅ Concluída |
| 1 | Modelo de dados e seed | Coleção `agentes_publicos` (50 parlamentares) + `termos_de_busca` | ✅ Concluída |
| 2 | Motor de ingestão (Web) | Google News RSS + Trafilatura | ✅ Concluída |
| 3 | Scrapers de redes sociais | Twitter, Instagram, Facebook | ✅ Concluída |
| 4 | Scrapers multimídia/mensageria | YouTube, Telegram | ✅ Concluída |
| 5 | Pipeline NLP e persistência | Limpeza (pandas) + sentimento (VADER PT) + Firestore | ✅ Concluída |
| 6 | Métricas agregadas | `metricas` por geral/cidade/agente + série diária | ✅ Concluída |
| 7 | Dashboard PWA | KPIs, filtros, gráficos, tempo real | ✅ Concluída |
| 8 | Controle de acesso (owner) | Coleção `usuarios` + script de owner | ✅ Concluída |
| 9 | **Deploy (Firebase Hosting)** | PWA publicado + `firebase.json`/`.firebaserc` | ✅ Concluída |
| 10 | **Valoração financeira da mídia** | Tabela R$/espaço + `valor_estimado` no pipeline/dashboard | ⏳ Pendente |
| 11 | Agendamento da ingestão | Cloud Scheduler / cron | ⏳ Pendente |
| 12 | Regras de Security (RBAC) | Firestore Rules por papel | ⏳ Pendente |
| 13 | Cobertura TV/Rádio/Impresso | Transcrição + valoração de falas | ⏳ Pendente |
| 14 | **Go live** | Homologação, monitoramento, documentação final | ⏳ Pendente |

**Status total:** 9 concluídas · 0 em andamento · 5 pendentes.

---

## Sprint 0 — Setup do Projeto ✅

**Objetivo:** Fundação do repositório e convenções.
- Inicialização do repositório Git (branch `main`) e remote GitHub (`renato0503/ValorPublico`).
- Estrutura de pastas `backend/` e `frontend/`.
- `.gitignore` robusto (credenciais, chaves, cookies, dados, logs).
- `.env.example` como template de configuração.
- Política de segurança: nunca versionar `.env`, `serviceAccountKey*`, `firebase-config.js`.

## Sprint 1 — Modelo de Dados e Seed ✅

**Objetivo:** Popular `agentes_publicos` com os 50 parlamentares.
- Coleção `agentes_publicos`: `nome_urna`, `cidade`, `partido`, `cargo`, `genero`, `termos_de_busca`.
- Script `seed_firebase.py` com roster embutido (27 Cuiabá + 23 Várzea Grande).
- Geração automática de `termos_de_busca` (nome + cargo + partido, com/sem acento).
- Validação de cobertura (27/23) antes de gravar; escrita idempotente (`merge`).

## Sprint 2 — Motor de Ingestão (Web / Mídia Tradicional) ✅

**Objetivo:** Capturar menções em portais de notícias.
- Scraper `web_scraper.py`: Google News RSS (pt-BR) + `feedparser`.
- Extração de texto limpo via `Trafilatura` (remoção de boilerplate, pronto p/ NLP/RAG).
- Cliente HTTP furtivo `httpx[http2]` com headers stealth e rotação de proxies.

## Sprint 3 — Scrapers de Redes Sociais ✅

**Objetivo:** Twitter/X, Instagram e Facebook.
- `twitter_scraper.py`: `twscrape` (GraphQL interno), pool de contas SQLite, cookies `auth_token`/`ct0`, rotação em HTTP 429.
- `instagram_scraper.py`: `instaloader` com sessão/cookies injetados + limite conservador.
- `facebook_scraper.py`: `Playwright` + stealth (a lib `facebook-scraper` está morta desde 2022), cookies de navegador, rolagem humana.

## Sprint 4 — Scrapers Multimídia e Mensageria ✅

**Objetivo:** YouTube e Telegram.
- `youtube_scraper.py`: `yt-dlp` (metadados/comentários) + `youtube-transcript-api` (transcrição das falas — rica p/ sentimento).
- `telegram_scraper.py`: `Telethon` (MTProto autenticado), canais/grupos abertos; evita clones do Pyrogram (Operação Navy Ghost).

## Sprint 5 — Pipeline NLP e Persistência ✅

**Objetivo:** Normalizar, deduplicar, classificar sentimento e gravar.
- `processing/cleaner.py`: `pandas` — remove URL/emoji/boilerplate, deduplica por `(agente_id, id_externo)`.
- `processing/sentiment.py`: VADER expandido com léxico em português + negações (positivo/negativo/neutro).
- `storage/firestore_repo.py`: grava `clippings` em subcoleção com batch de 500 e merge (idempotente).
- `scraper/orchestrator.py`: paralelismo `asyncio` (async scrapers) + `ThreadPoolExecutor` (sync), resumo de execução.

## Sprint 6 — Métricas Agregadas ✅

**Objetivo:** Dados prontos para leitura leve em tempo real.
- Script `atualizar_metricas.py` calcula e grava:
  - `metricas/geral` — KPIs globais.
  - `metricas_por_cidade/<slug>` — visão por cidade.
  - `metricas_por_agente/<id>` — visão por parlamentar.
  - `metricas_diarias/serie` — série por dia/plataforma.
- Inclui distribuição por categoria e sentimento + Top 10 fontes.

## Sprint 7 — Dashboard PWA ✅

**Objetivo:** Interface de BI responsiva e instalável.
- `index.html` + `css/styles.css`: layout dark, KPIs, painéis, ranking.
- `js/app.js`: filtros dinâmicos (cidade/parlamentar), `onSnapshot` em tempo real, estados de vazio/erro.
- `js/charts.js`: Chart.js — série temporal + rosca de share de mídia.
- `manifest.json` + `sw.js` + ícones: offline-first e instalável.

## Sprint 8 — Controle de Acesso (owner) ✅

**Objetivo:** Identificar o administrador da plataforma.
- Coleção `usuarios/{uid}` com `papel`, `ativo`, timestamps.
- Script `criar_owner.py` grava o proprietário como `owner`.
- Base para RBAC (regras de Firestore Security na Sprint 12).

## Sprint 9 — Deploy (Firebase Hosting) ✅

**Objetivo:** Publicar o PWA em produção.
- [x] `firebase.json` — hosting, `cleanUrls`, rewrite SPA, headers de cache (sw.js no-cache).
- [x] `.firebaserc` — projeto `valorpublico-b1e6d`.
- [x] `.gitignore` — `.firebase/` (cache local com tokens).
- [x] `firebase login` + `firebase deploy`.
- [x] Validação de `https://valorpublico-b1e6d.web.app` (todos os recursos 200 OK).
- **Produção:** https://valorpublico-b1e6d.web.app

## Sprint 10 — Valoração Financeira da Mídia ⏳

**Objetivo:** Converter menções em R$ (espaço publicitário equivalente).
- Tabela de `R$/espaço` por veículo/plataforma (Web, TV, Rádio, Impresso, Redes).
- Cálculo de `valor_estimado` no pipeline de ingestão (antes da persistência).
- Exibição da valoração por veículo e total no dashboard (KPI + Top 10).
- Persistência do `valor_estimado` nos clippings e nas métricas.

## Sprint 11 — Agendamento da Ingestão ⏳

**Objetivo:** Execução automática e recorrente do motor.
- Cloud Scheduler (cron) disparando o job de ingestão.
- Alternativa: GitHub Actions / cron local para MVP.
- Roda `run_ingestao.py` e depois `atualizar_metricas.py`.

## Sprint 12 — Regras de Security (RBAC) ⏳

**Objetivo:** Proteger o Firestore por papel de usuário.
- Firestore Security Rules: leitura/escrita condicionada ao `papel` em `usuarios/{uid}`.
- Proteger `agentes_publicos`, `clippings`, `metricas` e `usuarios`.
- Testes de regras (Emulator Suite).

## Sprint 13 — Cobertura TV, Rádio e Impresso ⏳

**Objetivo:** Ampliar fontes para mídia audiovisual e impressa.
- Transcrição de falas (speech-to-text) para TV/Rádio.
- Captura de matérias de jornais impressos.
- Valoração específica e sentimento sobre falas transcritas.

## Sprint 14 — Go Live ⏳

**Objetivo:** Entrega final em produção.
- Homologação completa do pipeline (ingestão → métricas → dashboard).
- Monitoramento (logs, alertas de erro, health checks).
- Documentação final (README + context.md + implementation.md atualizados).
- Comunicação e onboarding do usuário final.
