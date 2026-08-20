# ValorPúblico — Plano de Implementação (Sprints)

> Roteiro de execução da plataforma, da base até o **go live** completo.
> Atualizado em: 19/08/2026 (fim do dia).

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
| 9 | **Deploy (Firebase Hosting)** | PWA publicado em `valorpublico.web.app` | ✅ Concluída |
| 10 | **Valoração financeira da mídia** | Tabela R$/espaço + `valor_estimado` no pipeline/dashboard | ✅ Concluída |
| 15 | **Layout — Fundação visual** | Dark mode de alto padrão, tipografia, grid assimétrico | ✅ Concluída |
| 16 | **Layout — KPIs e tendência** | Indicadores de tendência nos KPIs | ✅ Concluída |
| 17 | **Layout — Gráficos** | Sentimento em donut, share + valoração 1/2+1/2 | ✅ Concluída |
| 18 | **Layout — Tabela e responsividade** | Top 10 full-width, sticky, media queries mobile | ✅ Concluída |
| — | **Ingestão Web (retomada)** | Completar clippings dos 50 agentes (13/50 ok) | ✅ Concluída (50/50, 1.510 clippings) |
| 11 | Agendamento da ingestão | Cloud Scheduler / cron | ✅ Concluída (GitHub Actions + rotina local) |
| 12 | Regras de Security (RBAC) | Firestore Rules por papel | ✅ Concluída |
| 13 | Cobertura TV/Rádio/Impresso | Transcrição + valoração de falas | ⏳ Pendente |
| 14 | **Go live** | Homologação, monitoramento, documentação final | ⏳ Pendente |

**Status total:** 18 sprints concluídas · 2 pendentes.

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
- [x] `firebase.json` — hosting (2 targets), `cleanUrls`, rewrite SPA, headers de cache.
- [x] `.firebaserc` — projeto `valorpublico-b1e6d` + targets `valorpublico` e `principal`.
- [x] `.gitignore` — `.firebase/` (cache local com tokens).
- [x] `firebase login` + `firebase deploy`.
- [x] Correção do service worker (network-first p/ JS, bump do cache) e do header de cache dos JS (evita MIME `text/html`).
- [x] Config do Firebase embutida no `js/firebase-init.js` (elimina dependência do `firebase-config.js`).
- **Produção:** https://valorpublico.web.app (site principal) e https://valorpublico-b1e6d.web.app

## Sprint 10 — Valoração Financeira da Mídia ✅

**Objetivo:** Converter menções em R$ (espaço publicitário equivalente).
- [x] Tabela `tabela_midia/geral` — CPM por plataforma + R$/matéria por veículo (configurável).
- [x] `processing/valoracao.py` — `Valorador` calcula `valor_estimado` (CPM por alcance p/ redes; tabela p/ Web).
- [x] Integrado ao `Orchestrator` (após sentimento, antes de persistir).
- [x] Métricas incluem `valoracao_por_plataforma` e `valoracao_por_categoria`.
- [x] Dashboard: KPI de valoração + gráfico de valoração por plataforma + coluna de valor no Top 10.

## Sprint 11 — Agendamento da Ingestão ✅

**Objetivo:** Execução automática e recorrente do motor.
- [x] GitHub Actions `.github/workflows/ingestao.yml` — cron diário (06:30/18:30 UTC) rodando `run_ingestao.py` + `atualizar_metricas.py`; credenciais via secrets (`FIREBASE_DATABASE_URL`, `FIREBASE_SERVICE_ACCOUNT_B64`).
- [x] Rotina local `backend/scripts/rotina_diaria.ps1` — alternativa MVP no Windows (Agendador de Tarefas).
- [ ] (Alternativa futura) Cloud Scheduler disparando job em ambiente serverless.

## Sprint 12 — Regras de Security (RBAC) ✅

**Objetivo:** Proteger o Firestore por papel de usuário.
- [x] `firestore.rules` — dashboard é público (leitura liberada em `agentes_publicos`, `metricas*`, `tabela_midia`); escrita **bloqueada** no cliente (backend usa Admin SDK, que ignora regras).
- [x] `usuarios/{uid}` — cada usuário lê/edita apenas o próprio documento (base para RBAC futuro).
- [x] `clippings`, `execucoes_ingestao` e coleções não listadas — negadas ao cliente.
- [x] Registrado no `firebase.json` (`firestore.rules` + `firestore.indexes.json`) e deployado.
- [ ] (Pendente) Testes automatizados de regras (Emulator Suite).

## Sprints 15–18 — Layout do Dashboard (Painel Executivo) ✅

**Objetivo:** Upgrade visual para um painel executivo de alto padrão em dark mode.
- **15 — Fundação visual:** fundo Slate 900, cards Slate 800 com bordas sutis e sombra; tipografia Inter; rótulos/eixos em Slate 400 e KPIs grandes/bold.
- **16 — KPIs e tendência:** 4 cards com indicador de tendência ("+X% esta semana", verde/vermelho) calculado pela série temporal.
- **17 — Gráficos:** grid assimétrico — série temporal (2/3) + sentimento em donut (1/3); share de mídia + valoração por plataforma (1/2+1/2).
- **18 — Tabela e responsividade:** Top 10 full-width com cabeçalho sticky, hover e colunas numéricas à direita; media queries que empilham os grids em mobile.
- **Deploy:** refatoração publicada em `https://valorpublico.web.app`.

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

## Estado Atual (20/08/2026)

- ✅ 50 agentes (`agentes_publicos`) + `tabela_midia/geral` repopulados.
- ✅ **Ingestão Web completa** — 50/50 agentes, **1.510 clippings** (R$ 609.650 em valoração, 227 veículos).
- ✅ **Métricas recalculadas** — `metricas/geral` + 2 cidades + 50 agentes (`atualizar_metricas.py`).
- ✅ **Owner recriado** — `usuarios/PS7XKpuuQHdw4wUsTjkxwhHBJfC3` (`criar_owner.py`).
- ✅ **Firestore Security Rules** (`firestore.rules`) — leitura pública do dashboard; escrita só via Admin SDK.
- ✅ **Sprint 11 (agendamento)** — GitHub Actions `.github/workflows/ingestao.yml` + rotina local `rotina_diaria.ps1`.
- ✅ **Deploy atualizado** — hosting + regras publicados em `https://valorpublico.web.app`.
- ⏳ **A fazer (ordem sugerida):**
  1. Validar o dashboard no navegador (hard refresh / limpar cache do SW v3).
  2. Configurar secrets no GitHub (`FIREBASE_DATABASE_URL`, `FIREBASE_SERVICE_ACCOUNT_B64`) para o workflow.
  3. Ativar YouTube/Telegram e configurar credenciais das redes sociais (Twitter/Instagram/Facebook).
  4. Sprint 13 (TV/Rádio/Impresso) e Sprint 14 (Go live).
