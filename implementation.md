# ValorPúblico — Plano de Implementação (Sprints)

> Roteiro de execução da plataforma, da base até o **go live** e melhorias contínuas.
> Atualizado em: 20/08/2026 (go live + sessão de auditoria, destrinche de mídia e análises lexicais).

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
| 15–18 | **Layout do painel executivo** | Dark mode, KPIs com tendência, gráficos, responsividade | ✅ Concluída |
| — | **Ingestão Web (retomada)** | Completar clippings dos 50 agentes | ✅ Concluída (50/50, 1.510 clippings) |
| 11 | Agendamento da ingestão | GitHub Actions (cron) + rotina local | ✅ Concluída |
| 12 | Regras de Security (RBAC) | Firestore Rules por papel | ✅ Concluída |
| 13 | Cobertura TV/Rádio/Impresso | Transcrição + valoração de falas | ✅ Concluída |
| 14 | **Go live** | Homologação, monitoramento, documentação final | ✅ Concluída |
| 19 | **Auditoria, destrinche de mídia e YouTube** | Classificador de mídia, YouTube ativo, export CSV | ✅ Concluída |
| 20 | **Analytics e análise lexical (IRAMUTEQ)** | Série por sentimento, nuvem interativa, análises lexicais | ✅ Concluída |

**Status total:** 21 sprints/entregas concluídas · pendências pontuais listadas abaixo.

---

## Sprint 0 — Setup do Projeto ✅
Fundação do repositório, estrutura `backend/`+`frontend/`, `.gitignore` robusto,
`.env.example`, política de segurança (nunca versionar credenciais).

## Sprint 1 — Modelo de Dados e Seed ✅
`agentes_publicos` com 50 parlamentares (27 Cuiabá + 23 Várzea Grande), `termos_de_busca`
gerados automaticamente (nome + cargo + partido, com/sem acento), escrita idempotente.

## Sprint 2 — Motor de Ingestão (Web) ✅
`web_scraper.py` (Google News RSS + `feedparser` + `Trafilatura`), cliente furtivo `httpx[http2]`
com delays randômicos, retry/backoff e rotação de proxies.

## Sprint 3 — Scrapers de Redes Sociais ✅
`twitter_scraper.py` (`twscrape`), `instagram_scraper.py` (`instaloader`),
`facebook_scraper.py` (`Playwright` + stealth). **Requerem credenciais reais** para operar.

## Sprint 4 — Scrapers Multimídia e Mensageria ✅
`youtube_scraper.py` e `telegram_scraper.py` (Telethon). YouTube reescrito para operar via CLI
`yt-dlp` + legendas automáticas (ver Sprint 19); Telegram exige `API_ID`/`API_HASH`.

## Sprint 5 — Pipeline NLP e Persistência ✅
`processing/cleaner.py` (pandas: remove URL/emoji/boilerplate, deduplica, trata `NaT`),
`processing/sentiment.py` (VADER + léxico PT), `storage/firestore_repo.py` (batch 500, merge).

## Sprint 6 — Métricas Agregadas ✅
`atualizar_metricas.py` grava `metricas/geral`, `metricas_por_cidade/<slug>`,
`metricas_por_agente/<id>` com distribuição por categoria/sentimento, Top 10 e série diária.

## Sprint 7 — Dashboard PWA ✅
`index.html` + `css/styles.css` + `js/app.js` + `js/charts.js` (Chart.js), filtros
cidade/parlamentar, `onSnapshot` em tempo real, `manifest.json` + `sw.js` (offline-first).

## Sprint 8 — Controle de Acesso (owner) ✅
Coleção `usuarios/{uid}` + `criar_owner.py` (base para RBAC na Sprint 12).

## Sprint 9 — Deploy (Firebase Hosting) ✅
`firebase.json` (2 targets), `.firebaserc`, correções de cache/MIME do SW,
config embutida em `js/firebase-init.js`. Produção: https://valorpublico.web.app

## Sprint 10 — Valoração Financeira da Mídia ✅
`tabela_midia/geral` (CPM + veículos), `processing/valoracao.py` (CPM por alcance p/ redes;
tabela p/ Web/Impresso), integrado ao `Orchestrator` e ao dashboard.

## Sprint 11 — Agendamento da Ingestão ✅
GitHub Actions `.github/workflows/ingestao.yml` (cron 06:30/18:30 UTC) + `rotina_diaria.ps1`.
Secrets configurados (`FIREBASE_DATABASE_URL`, `FIREBASE_SERVICE_ACCOUNT_B64`).

## Sprint 12 — Regras de Security (RBAC) ✅
`firestore.rules` — leitura pública do dashboard; escrita restrita ao Admin SDK.
- [ ] (Pendente) Testes automatizados de regras (Emulator Suite).

## Sprint 13 — Cobertura TV, Rádio e Impresso ✅
`tv_radio_scraper.py` e `impresso_scraper.py` com valoração específica.
- [ ] (Ajuste de campo) Ampliar `MIDIA_VIDEOS_POR_CANAL` e canais de rádio reais; hoje os
  vídeos atuais não citam vereadores (0 clippings) e os portais não expõem RSS.

## Sprint 14 — Go Live ✅
Homologação (50/50 agentes, 1.510+ clippings), monitoramento (`ultima_execucao`), README,
context/implementation atualizados, secrets + workflow validados.

## Sprint 19 — Auditoria, Destrinche de Mídia e YouTube ✅

**Objetivo:** destrinchar a origem "Web" por categoria de mídia e ativar o YouTube.
- [x] **Classificador de mídia** (`processing/classificador_midia.py`) — mapeia cada veículo/domínio
  para Portal, Rádio, TV, Jornal Impresso, Governo, Redes Sociais, YouTube, Telegram.
- [x] **Métricas destrincadas** — `atualizar_metricas.py` usa o classificador no share de mídia
  (correção: `set()` sobrescreve o doc inteiro — evita merge profundo de mapas).
- [x] **YouTube ativo** — `youtube_scraper.py` reescrito para CLI `yt-dlp` (busca pelo nome do
  agente) + transcrição via **legendas automáticas** (o `youtube-transcript-api` retornava vazio);
  parser VTT com merge por sobreposição de palavras; cache 1x por vídeo/canal.
- [x] **TV/Rádio/Impresso robustos** — `tv_radio_scraper.py` e `impresso_scraper.py` com cache
  por canal/site (1x por execução) e transcrição por legendas.
- [x] **Ingestão paralela entre agentes** — `Orchestrator` com `asyncio.Semaphore`
  (`PARALELISMO_AGENTES`, padrão 4) — redução de ~4x no tempo.
- [x] **Export CSV de auditoria** — `scripts/exportar_clippings.py` → `data/export/clippings_YYYYMMDD.csv`
  (UTF-8 BOM + `;`, colunas de agente + clipping + metadados + `categoria_midia`).

## Sprint 20 — Analytics e Análise Lexical (IRAMUTEQ) ✅

**Objetivo:** enriquecer o dashboard e habilitar análises lexicais do corpus (estilo IRAMUTEQ).
- [x] **Série temporal por sentimento** — 3 linhas no gráfico (Positivo verde, Neutro azul,
  Negativo vermelho) com cores mapeadas **por rótulo** (fix de cores).
- [x] **Nuvem de palavras interativa** — `metricas` com `nuvem_geral` + `nuvem_por_mes`;
  dashboard com filtro de período (mês) e tooltip de contagem.
- [x] **Botão "Atualizar"** no header — limpa caches do SW, desregistra o SW e recarrega
  (traz as atualizações do desenvolvimento).
- [x] **Stopwords e limpeza de corpus** — `processing/nuvem.py` com stopwords PT + remoção de
  ruído RSS (hex-colors, nomes de veículos).
- [x] **Análises lexicais IRAMUTEQ** — `processing/lexical.py` + `scripts/analise_lexical.py`:
  frequência (global/por mês), especificidade (chi2 por período), co-ocorrência + grafo de
  similaridade, AFC (SVD palavra×período) e CHD (Ward + palavras características). Saídas em
  `data/export/lexical/` (CSV + JSON + resumo).
- [ ] (Pendente) Visualização no frontend: mapa fatorial (AFC), grafo de similaridade e
  dendrograma da CHD (os dados já são gerados).

## Estado Atual (20/08/2026)

- ✅ 50 agentes (`agentes_publicos`) + `tabela_midia/geral` (8 CPM + 13 veículos).
- ✅ **Ingestão Web + YouTube** — 50/50 agentes, **1.801 clippings**.
- ✅ **Share de mídia destrincado** — Portal 1.177, Jornal Impresso 338, YouTube 156,
  Governo 77, TV 36, Rádio 13 (+ 2 Redes, 2 Outros).
- ✅ **Métricas com série por sentimento e nuvem** — `metricas/geral` + 2 cidades + 50 agentes.
- ✅ **Export CSV** — `data/export/clippings_20260820.csv` (1.801 linhas, com `categoria_midia`).
- ✅ **Análises lexicais** — `data/export/lexical/` (frequência, especificidade, co-ocorrência,
  AFC, CHD — 4 classes temáticas).
- ✅ **Dashboard** — série por sentimento, nuvem interativa, botão Atualizar, cores corretas;
  deployado em https://valorpublico.web.app.
- ✅ **Firestore Rules** + owner + GitHub Actions — operando.
- ⏳ **Pendências pós-go-live:**
  1. Credenciais das redes sociais (Twitter/Instagram/Facebook) e Telegram (`API_ID`/`API_HASH`).
  2. TV/Rádio/Impresso com dados reais (ampliar canais/janela; hoje 0 menções).
  3. Incluir TV/Rádio/Impresso no cron do GitHub Actions (secrets `TV_CANAIS`/`RADIO_CANAIS`/`IMPRESSO_SITES`).
  4. Visualização das análises lexicais no frontend (AFC/grafo/dendrograma).
5. Ajustar CPM/valores conforme tabela publicitária real.
6. Testes de regras no Emulator Suite.

---

# Fase 2 — Benchmarking DSM (Dinâmica MT)

> Objetivo: levar o ValorPúblico ao mesmo nível funcional da ferramenta de
> clipping/análise de mídia da **DSM (https://dsm.dinamicamt.com.br)** — mapeada por
> engenharia reversa (login real + captura de UI/rotas) em 20/08/2026 — somando-a às
> funcionalidades já existentes (valoração, análise lexical IRAMUTEQ, nuvem de palavras).

## Funcionalidades da DSM (benchmark mapeado)

| Módulo | Funcionalidades observadas |
|---|---|
| **Dashboard (Início)** | Filtros Hoje/7d/30d/Personalizado + Categorias; KPIs (avaliações, menções pos/neu/neg); veículos monitorados por tipo (WEB/RÁDIO/TV/IMPRESSO/REVISTAS); insights (maior cobertura, veículo destaque, tendência); Top Veículos com filtro por tipo; volume semanal; análise de sentimento (donut %); notícias recentes |
| **Relatórios (Pesquisa avançada)** | Filtros período/estado/município/avaliação/avaliação IA/tipo de veículo/veículo/categorias/termos; lista de notícias (veículo, editoria, tipo, categorias, avaliação); caixa de seleção; **somatório de espaço** (site=caracteres, rádio=tempo, TV=tempo, impresso=cm²), **somatório de valor (R$)** e **somatório de sentimento** |
| **Análise de Mídia** | Abas Análise Estatística / Qualitativa / Repercussão Negativa; filtros data inicial/final, assuntos (busca), tipo de veículo; **EXPORTAR PDF** |
| **Detalhe de notícia** | Valoração (R$ calculado, valor veículo, base de valoração), categorias (agentes/temas), conteúdo e palavras-chave |
| **Painel do cliente** | Busca por título/categoria/estado; categorias WEB/RÁDIO/TV/IMPRESSO; listas de agentes |
| **Redes Sociais** | Em desenvolvimento na DSM (solicitação de acesso antecipado) |

## Sprints de Benchmarking DSM

| Sprint | Tema | Entrega principal | Status |
|---|---|---|---|
| 21 | Filtros de período no dashboard | Hoje / 7d / 30d / Personalizado + categorias (KPIs, série, share, top) | ✅ Concluída |
| 22 | Insights Principais e Top Veículos | Cards de destaque (maior cobertura, veículo destaque, tendência) + top com filtro por tipo | ✅ Concluída |
| 23 | Categorias/temas por notícia | Classificar cada clipping em temas/assuntos (reuso das análises lexicais) | ✅ Concluída |
| 24 | Detalhe de notícia | Modal com valoração (R$/veículo/base), categorias, conteúdo e palavras-chave | ✅ Concluída |
| 25 | Pesquisa avançada / Relatórios | Filtros múltiplos + somatório de espaço/valor/sentimento | ✅ Concluída |
| 26 | Análise de Mídia | Abas estatística/qualitativa/repercussão negativa + filtro de assuntos | ✅ Concluída |
| 27 | Exportação PDF de relatório | Gerar PDF com filtros aplicados (via impressão do navegador) | ✅ Concluída |

### Implementação da Fase 2 (resumo)

- **21 — Períodos:** `atualizar_metricas.py` agora grava `metricas/*.por_periodo` com janelas
  `hoje`, `7d` e `30d` (cada uma com KPIs, categorias, sentimento, top veículos e série);
  o frontend alterna entre elas sem nova consulta.
- **22 — Insights/Top:** `metricas/*.insights` (maior cobertura, veículo em destaque, tendência
  positiva, pct positivo/negativo) e `top_veiculos` com `categoria_midia` por veículo; seção de
  Insights no dashboard + filtro de tipo no Top 10.
- **23 — Temas:** `processing/temas.py` (16 temas por regras de palavras-chave) +
  `scripts/classificar_temas.py` (backfill idempotente, `categorias` no clipping);
  `distribuicao_temas` nas métricas; coluna `temas` no CSV.
- **24 — Detalhe:** modal que abre o clipping (valoração R$/alcance/plataforma, categorias,
  palavras-chave, conteúdo e link original).
- **25 — Relatório:** botão "Relatório" no header + modal de pesquisa avançada com filtros
  (período, tipo de mídia, sentimento), somatórios (menções, valor R$, espaço em caracteres)
  e lista por categoria.
- **26 — Análise de Mídia:** painel com abas Estatística / Qualitativa / Repercussão Negativa.
- **27 — PDF:** botão "Exportar PDF" (imprime a view de relatório via `window.print()`).
- **Deploy:** Fase 2 publicada em https://valorpublico.web.app.

### Decisões e pendências da Fase 2

- **Avaliação IA** (DSM usa IA): no ValorPúblico o sentimento segue VADER; integrar LLM
  (ex.: Gemini/OpenAI) é custo a decidir (Sprint 25). Heurísticas já cobrem os temas.
- **Somatório de espaço** por tipo (site=caracteres, rádio/TV=tempo, impresso=cm²) requer
  registrar metadados de duração/cm² na ingestão (TV/Rádio/Impresso ainda com 0 dados).
- **PDF nativo:** hoje via `window.print()`; gerar PDF servido por backend (reportlab) fica
  como melhoria futura se houver necessidade de relatórios assinados/brandados.
- **Redes sociais:** a própria DSM ainda está em desenvolvimento; manter YouTube ativo e
  configurar credenciais das demais (pendência já listada).

### Sprint 21 — Filtros de período no dashboard

**Objetivo:** permitir escolher o período (Hoje, Últimos 7 dias, Últimos 30 dias, Personalizado)
e por categoria, impactando KPIs, série temporal, share e top veículos.

- **Backend:** enriquecer `metricas/geral` (e por cidade/agente) com **séries por janela** —
  `serie_sentimento_7d`, `serie_sentimento_30d`, `dias_7d`, `dias_30d` — e `total_por_periodo`
  já derivado no servidor (evita filtro pesado no cliente).
- **Frontend:** seletor de período + categorias; os gráficos/KPIs re-renderizam a partir do
  subconjunto de séries escolhido. Reuso da série por sentimento já existente.
- **Modelo:** manter `metricas/*` com janelas pré-computadas (padrão atual de performance).

### Sprint 22 — Insights Principais e Top Veículos

**Objetivo:** cards de "Insights" e ranking de veículos com filtro por tipo de mídia.

- **Backend:** `metricas/geral.insights` = `{maior_cobertura, veiculo_destaque,
  tendencia_positiva, pct_positivo}` e `top_veiculos` com `categoria_midia` por veículo.
- **Frontend:** seção "Insights Principais" (3 cards) + filtro de tipo no Top 10 (Geral /
  WEB / RÁDIO / TV / IMPRESSO).
- **Reuso:** classificador de mídia (`classificador_midia.py`) já fornece a categoria por veículo.

### Sprint 23 — Categorias/temas por notícia

**Objetivo:** além dos agentes, classificar cada clipping em **temas/assuntos** (ex.: Saúde,
Educação, CPI, Eleições), como a DSM faz com "Categorias".

- **Backend:** gerar categorias por clipping — (a) automática por palavras-chave/temas das
  análises lexicais (classes da CHD); (b) manual/configurável por regra de termos
  (`categoria_midia` + `categorias` array no doc do clipping).
- **Modelo:** adicionar campo `categorias: array<string>` no clipping e `distribuicao_categorias_tema`
  nas métricas; incluir no CSV de exportação.
- **Filtros:** permitir buscar/filtrar relatórios por categoria.

### Sprint 24 — Detalhe de notícia

**Objetivo:** página individual do clipping com valoração detalhada, categorias e conteúdo.

- **Frontend:** rota `/noticias/{id}/detalhes` (SPA) mostrando título, veículo, editoria, tipo,
  data; valoração (R$ calculado = `valor_estimado`, valor veículo da tabela, base de valoração
  = alcance/CPM); categorias; conteúdo integral; palavras-chave (top tokens da análise lexical).
- **Backend:** endpoint/query por `id_clipping` (já há subcoleção por agente); agregar
  `valor_veiculo`, `base_valoracao` e `palavras_chave` no doc do clipping.

### Sprint 25 — Pesquisa avançada / Relatórios

**Objetivo:** listar notícias com filtros múltiplos e somatórios (espaço, valor, sentimento).

- **Backend:** endpoint de pesquisa com filtros (período, estado, município, avaliação,
  avaliação IA, tipo de veículo, veículo, categorias, termos) + agregados:
  `somatório espaço` (site=caracteres, rádio=minutos, TV=minutos, impresso=cm²),
  `somatório valor (R$)` e `somatório sentimento`.
- **Frontend:** tela de Relatórios com formulário de filtros, lista selecionável (checkboxes),
  rodapé com somatórios e ações (exportar PDF).
- **Reuso:** classificação `categoria_midia`, sentimento e `valor_estimado` já existentes.

### Sprint 26 — Análise de Mídia

**Objetivo:** abas Estatística, Qualitativa e Repercussão Negativa sobre o corpus.

- **Estatística:** KPIs do período (menções, sentimento, share, top veículos, série).
- **Qualitativa:** usar as análises lexicais IRAMUTEQ (frequência, especificidade, co-ocorrência,
  AFC, CHD) para apresentar temas/classes e palavras características.
- **Repercussão Negativa:** clippings com sentimento negativo + termos de crise, com ranking
  por veículo e período.
- **Frontend:** abas com visualizações (já temos nuvem; integrar mapa fatorial/grafo/dendrograma).

### Sprint 27 — Exportação PDF de relatório

**Objetivo:** gerar PDF do relatório com os filtros aplicados (auditoria/apresentação).

- **Backend:** gerar PDF via `reportlab`/`weasyprint` (a decidir) a partir dos dados filtrados
  (KPIs, somatórios, lista, análises lexicais). Servir como download.
- **Frontend:** botão "Exportar PDF" nas telas de Relatórios e Análise de Mídia.
- **Reuso:** dados já agregados nos módulos anteriores.

## Dependências e ordem sugerida

- **21 e 22** (dashboard) independem das demais → primeiro.
- **23** (categorias/temas) habilita **24** (detalhe) e **25** (pesquisa por categoria).
- **25** e **26** reusam **23** (temas) e a análise lexical já existente.
- **27** (PDF) é o fechamento, consumindo **25** e **26**.

## Riscos / decisões abertas

- **Filtros por período** — pré-computar janelas (hoje/7d/30d) no Firestore é barato; janela
  "personalizada" exigirá query no cliente ou endpoint dinâmico (decidir na Sprint 21).
- **Avaliação IA** (DSM) — hoje o sentimento é VADER; avaliação IA exige LLM (custo). Decidir
  se usa heurística/regras ou integra uma API de LLM (Sprint 25).
- **Somatório de espaço** — precisa registrar tamanho do conteúdo (caracteres) por clipping e
  metadados de duração (rádio/TV) e cm² (impresso) na ingestão.
- **PDF** — escolha da lib de geração e hospedagem (Cloud Function vs local no cron).
- **Redes sociais** — a própria DSM ainda está em desenvolvimento; manter YouTube ativo e
  configurar credenciais das demais (pendência já listada).