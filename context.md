# ValorPúblico — Contexto Estratégico

> Documento vivo de contexto da plataforma de **Business Intelligence (BI)** e
> **Monitoramento de Mídia** focada em inteligência política e institucional.
> Atualizado em: 20/08/2026 (pós go live — sessão de auditoria, destrinche de mídia e análises lexicais).

---

## 1. Visão Geral e Objetivo

**ValorPúblico** é uma plataforma de BI + Web Scraping/Clipping que consolida a
presença midiática e digital de agentes públicos, convertendo volume de menções,
alcance de audiência e valoração financeira espontânea da mídia em **inteligência
de imagem e reputação política**.

O objetivo central é responder, em tempo quase real:

- Quanto cada parlamentar é citado na mídia e nas redes sociais?
- Qual é o alcance (audiência) dessas menções?
- Qual é o valor financeiro espontâneo (espaço publicitário equivalente) gerado?
- Qual é o **sentimento** dos eleitores/comentadores (positivo, negativo, neutro)?
- Quais veículos e páginas são mais relevantes para cada agente?
- **Quais temas dominam o debate em cada período?** (análise lexical IRAMUTEQ)

## 2. Público-Alvo

| Segmento | Necessidade principal |
|---|---|
| **Pré-candidatos e candidatos** | Posicionamento, prova de volume de mídia, análise de concorrência |
| **Vereadores e mandatos ativos** | Prestação de contas, medição de engajamento, imagem pública |
| **Assessores de comunicação / marketing político** | Relatórios de clipagem, valoração de mídia espontânea, pautas |
| **Partidos e institutos de pesquisa** | Cruzamento de sentimento com intenção de voto, temas de campanha |
| **Consultorias políticas** | Inteligência competitiva, análise de temas e recomendações de pauta |

**Escopo geográfico inicial:** Mato Grosso — municípios de **Cuiabá** e **Várzea Grande**.

## 3. Escopo de Dados (Alvos Monitorados)

- **50 parlamentares municipais**:
  - **Cuiabá (MT):** 27 vereadores.
  - **Várzea Grande (MT):** 23 vereadores.
- Cada alvo é cadastrado como um **agente público** com variações de nome
  (`termos_de_busca`) usadas para varrer mídia e redes sociais.

### Fontes monitoradas
- **Mídia tradicional:** Web / portais de notícias (via Google News RSS + Trafilatura).
- **Redes sociais:** Twitter/X, Instagram, Facebook, **YouTube (ativo)**, Telegram.
- **Cobertura TV/Rádio/Impresso:** canais de notícia no YouTube (transcrição de falas) e jornais com edição digital.

## 4. Arquitetura Tecnológica

```
┌─────────────────────────────┐        ┌─────────────────────────────┐
│       BACKEND (Python)      │        │   FRONTEND (PWA / JS)       │
│  Motor de ingestão/scraping │        │   Dashboard de BI           │
│  Pipeline NLP de sentimento │        │   Filtros + KPIs + gráficos  │
│  Análises lexicais (IRAMUTEQ)│       │   Nuvem de palavras + mapa   │
│  Persistência (Firestore)   │        │   Tempo real (onSnapshot)    │
└──────────────┬──────────────┘        └──────────────┬──────────────┘
               │                                       │
               └───────────────► Firestore ◄───────────┘
                        (Google Firebase / NoSQL)
```

### Backend (Python)
- **Linguagem:** Python 3.12+.
- **Cliente HTTP furtivo:** `httpx[http2]` com headers stealth e rotação de proxy.
- **Resiliência:** delays randômicos, retry com backoff exponencial, rotação de IPs.
- **Paralelismo:** scrapers via `asyncio` + `ThreadPoolExecutor`; **agentes processados em paralelo** (semáforo, padrão 4) para acelerar a ingestão.
- **Processamento:** `pandas` para limpeza/deduplicação; NLP de sentimento via VADER
  expandido com léxico em português; **análises lexicais** com `numpy`/`scipy`/`sklearn`
  (frequência, especificidade, co-ocorrência, AFC e CHD/Ward).

### Scrapers implementados (conforme pesquisa 2026)
| Plataforma | Ferramenta | Observações |
|---|---|---|
| Twitter/X | `twscrape` | Exige cookies reais (`auth_token`, `ct0`); pool de contas SQLite + rotação em HTTP 429 |
| Instagram | `instaloader` | Sessão/cookies injetados; limite conservador p/ evitar ban por IP |
| Facebook | `Playwright` + stealth | `facebook-scraper` está morto desde 2022; exige cookies de navegador e rolagem humana |
| YouTube | `yt-dlp` (CLI) + legendas automáticas | Busca pelo nome do agente + transcrição das falas; ativo e coletando |
| Telegram | `Telethon` (MTProto) | Nunca usar clones do Pyrogram (Operação Navy Ghost); exige `API_ID`/`API_HASH` |
| Web/Notícias | Google News RSS + `Trafilatura` | Extração de texto limpo (boilerplate removido), pronto p/ RAG |
| TV/Rádio | `yt-dlp` (CLI) + legendas | Canais de notícia locais no YouTube; transcreve as falas dos telejornais |
| Impresso | RSS/Homepage + `Trafilatura` | Jornais com edição digital; valoração por tabela de veículos |

### Frontend (PWA)
- **Stack:** HTML5 + CSS3 + JavaScript (módulos ES6), Firebase JS SDK, Chart.js.
- **Recursos PWA:** `manifest.json`, Service Worker (offline-first), instalação, **botão "Atualizar"** que limpa o cache e recarrega os dados.
- **Dashboard:** KPIs executivos, **série temporal por sentimento (3 linhas)**, **nuvem de palavras interativa com filtro mensal**, share de mídia destrincado (Portal/Rádio/TV/Jornal/Governo/Redes), ranking Top 10 fontes, análise de sentimento e filtros por cidade/parlamentar.

## 5. Banco de Dados (Google Firebase Firestore — NoSQL)

### Coleção `agentes_publicos` (50 documentos)
| Campo | Tipo | Descrição |
|---|---|---|
| `nome_urna` | string | Nome de urna do parlamentar |
| `cidade` | string | Cuiabá ou Várzea Grande |
| `partido` | string | Sigla/nome do partido |
| `cargo` | string | Vereador / Vereadora |
| `genero` | string | M / F (define a flexão do cargo) |
| `termos_de_busca` | array<string> | Variações de nome + cargo + partido (com/sem acento) |

### Subcoleção `agentes_publicos/{id}/clippings`
| Campo | Tipo | Descrição |
|---|---|---|
| `id_clipping` | string | `plataforma_id_externo` |
| `plataforma` | string | Twitter, Instagram, Facebook, Web, YouTube, TV, Radio, Impresso, Telegram |
| `tipo` | string | Postagem, Comentário, Notícia |
| `texto_limpo` | string | Texto normalizado (limpo p/ NLP) |
| `sentimento` | string | positivo / negativo / neutro |
| `data_publicacao` | timestamp | Data da publicação |
| `autor` / `url` / `alcance` / `valor_estimado` | — | Metadados de fonte e audiência |
| `metadados` | map | Detalhes por plataforma (`veiculo`, `canal`, `origem`, etc.) |

### Coleções de métricas (otimizadas para o dashboard em tempo real)
- `metricas/geral` — KPIs globais + série por sentimento + nuvem de palavras.
- `metricas_por_cidade/<slug>` — visão por cidade.
- `metricas_por_agente/<id>` — visão por parlamentar.
- `tabela_midia/geral` — CPM por plataforma + R$/matéria por veículo.
- `usuarios/{uid}` — controle de acesso (papel `owner`, etc.).
- `execucoes_ingestao` — registro de cada execução do motor.

## 6. Regras de Negócio

1. Cada clipping pertence a **um agente** (via subcoleção) e a **uma plataforma**.
2. `termos_de_busca` são gerados automaticamente combinando nome, cargo (flexão
   por gênero) e partido, em versões com e sem acento (máx. de match).
3. Todo texto passa por **limpeza** (remoção de URL/emoji/boilerplate/RSS/hex-color) e
   **deduplicação** antes de entrar no Firestore.
4. O **sentimento** é classificado antes da persistência (VADER + léxico PT).
5. Métricas agregadas são **recalculadas** por script (não lidas no cliente),
   garantindo alta performance e leitura leve em tempo real.
6. A origem "Web" é **destrincada** em categoria de mídia (Portal, Rádio, TV, Jornal
   Impresso, Governo) por um classificador de veículo/domínio (`classificador_midia.py`).
7. **Segurança:** credenciais e chaves de serviço ficam **fora do git**
   (`.env`, `serviceAccountKey.json`, `firebase-config.js`).

## 7. KPIs do Dashboard

- Total de **veículos/fontes** monitoradas.
- **Audiência total** estimada (soma de alcance).
- **Valoração total** (R$) da mídia espontânea.
- Total de **clippings**.
- **Série temporal** de menções por dia, **discriminada por sentimento**.
- **Share de mídia** destrincado (Portal, Rádio, TV, Jornal, Governo, Redes, YouTube).
- **Análise de sentimento** (positivo/neutro/negativo — cores fixas: verde/azul/vermelho).
- **Top 10** veículos/páginas mais relevantes.
- **Nuvem de palavras** com filtro por período (mês).

## 8. Estrutura de Pastas

```
ValorPublico/
├── backend/
│   ├── config/settings.py          # env + configuração
│   ├── core/                       # firebase_client, logger
│   ├── scraper/                    # scrapers + orchestrator + models
│   ├── processing/                 # cleaner, sentiment, valoracao, classificador,
│   │                               # nuvem (palavras) e lexical (IRAMUTEQ)
│   ├── storage/                    # firestore_repo
│   ├── scripts/                    # seed, ingestão, métricas, export CSV,
│   │                               # análise lexical, owner, rotina
│   ├── data/                       # seeds / raw / processed / export (gitignored em parte)
│   ├── requirements.txt
│   └── .env.example                # template de configuração
├── frontend/                       # PWA (index.html, manifest, sw, css, js)
├── .github/workflows/ingestao.yml  # agendamento (cron diário)
├── context.md                      # este documento
├── implementation.md               # plano de sprints
└── README.md
```

## 9. Segurança e Boas Práticas

- Nunca versionar: `.env`, `*.json` de chaves, `serviceAccountKey*`,
  `firebase-config.js`, cookies/sessões, proxies.
- Antes de qualquer commit: revisar `git diff --cached` e varrer segredos.
- **Rotacionar chaves** de conta de serviço caso sejam expostas.
- Para escala real de scraping, usar **proxies residenciais/móveis** (o código
  já suporta `PROXY_LIST`).
- A API key web do Firebase (em `frontend/js/firebase-init.js`) é **pública por design**.

## 10. Estado Atual (20/08/2026)

- **Banco (Firestore):** pipeline completo operando.
  - ✅ `agentes_publicos` — 50 agentes (27 Cuiabá + 23 Várzea Grande), com `votos_2024`, `legislatura` e `termos_de_busca`.
  - ✅ `tabela_midia/geral` — CPM de 8 plataformas + 13 veículos (portal/impresso).
  - ✅ `clippings` — **1.801 clippings** (Web + YouTube com transcrição), 50 agentes.
  - ✅ `metricas` — regeneradas com **share destrincado**: Portal 1.177, Jornal Impresso 338, YouTube 156, Governo 77, TV 36, Rádio 13 (+ série por sentimento e nuvem de palavras).
  - ✅ `usuarios` — owner recriado (`criar_owner.py`).
- **Scrapers:**
  - ✅ **Web** — 100% dos agentes (Google News RSS).
  - ✅ **YouTube** — ativo (busca por nome + transcrição das falas via legendas automáticas).
  - ✅ **TV/Rádio/Impresso** — implementados e conectados, porém **0 clippings** no momento (os vídeos atuais dos canais locais não citam vereadores em legenda/título; os portais não expõem RSS).
- **Melhorias nesta sessão (auditoria e análise):**
  - ✅ **Classificador de mídia** (`processing/classificador_midia.py`) — destrincha a origem Web em Portal/Rádio/TV/Jornal/Governo.
  - ✅ **Nuvem de palavras** + **série temporal por sentimento** + **botão Atualizar** no dashboard (deployado).
  - ✅ **Exportação CSV** de auditoria (`scripts/exportar_clippings.py` → `data/export/clippings_20260820.csv`).
  - ✅ **Análises lexicais IRAMUTEQ** (`processing/lexical.py` + `scripts/analise_lexical.py`) — frequência, especificidade, co-ocorrência, AFC e CHD (dados em `data/export/lexical/`).
  - ✅ **Ingestão paralela entre agentes** (semáforo) — tempo de execução reduzido ~4x.
- **Fase 2 — Benchmarking DSM (sprints 21–27, deployado):**
  - ✅ **Filtros de período** (Hoje / 7d / 30d / Todo) nos KPIs, série, share e top (via `por_periodo` nas métricas).
  - ✅ **Insights Principais** (maior cobertura, veículo destaque, tendência) + **Top Veículos** com filtro por tipo.
  - ✅ **Temas/categorias por notícia** (`processing/temas.py` + backfill `classificar_temas.py`): 16 temas (Política/Câmara, Eleições, Governo, Justiça, Tecnologia...) com `distribuicao_temas` nas métricas e coluna `temas` no CSV.
  - ✅ **Detalhe de notícia** (modal: valoração, categorias, palavras-chave, conteúdo, link).
  - ✅ **Relatório / pesquisa avançada** (modal: filtros por período/tipo/sentimento + somatórios de menções/valor/espaço).
  - ✅ **Análise de Mídia** (abas Estatística / Qualitativa / Repercussão Negativa).
  - ✅ **Exportação PDF** (via impressão do navegador).
- **Segurança (Firestore Rules):** `firestore.rules` deployado (leitura pública do dashboard; escrita restrita ao Admin SDK).
- **Agendamento:** GitHub Actions `.github/workflows/ingestao.yml` (cron diário) + rotina local `backend/scripts/rotina_diaria.ps1`.
- **Frontend (PWA):** deployado em `https://valorpublico.web.app` (config embutida no `firebase-init.js`).
  - ⚠️ Se exibir dados antigos: use o botão **↻ Atualizar** no topo (limpa cache do SW e recarrega) ou **Ctrl+Shift+R**.

## 11. Próximos Passos

- [x] **Fase 2 — Benchmarking DSM (Dinâmica MT)** — implementada (sprints 21–27):
      filtros de período, insights, temas por notícia, detalhe de notícia, pesquisa
      avançada/relatórios, análise de mídia e exportação PDF. Detalhes em `implementation.md`.
- [ ] **Redes sociais (Twitter/Instagram/Facebook/Telegram)** — configurar credenciais (cookies/sessão/API) para ativar os scrapers; hoje só o YouTube opera sem credenciais.
- [ ] **TV/Rádio/Impresso** — ampliar a janela de vídeos por canal (`MIDIA_VIDEOS_POR_CANAL`) e buscar os canais oficiais corretos para as rádios (ex.: Rádio Capital FM não tem canal de notícias no YouTube); incluir TV/Rádio/Impresso no cron do GitHub Actions (adicionando `TV_CANAIS`/`RADIO_CANAIS`/`IMPRESSO_SITES` como secrets).
- [ ] **Dashboard — Análise Lexical visual:** mapa fatorial (AFC), grafo de similaridade e dendrograma da CHD no frontend (os dados já são gerados pelo backend).
- [ ] **Avaliação IA do sentimento** (alternativa ao VADER) — custo/LLM a decidir.
- [ ] **Ajustar CPM/valores** da tabela conforme a tabela publicitária real de cada veículo.
- [ ] **Alertas de erro/health check** externo para o workflow (opcional).
- [ ] **Testes de regras** no Emulator Suite (aprimoramento do RBAC).

## 12. Análises Lexicais (estilo IRAMUTEQ)

O backend gera análises lexicais sobre o corpus de clippings (Web + YouTube + TV/Rádio),
replicando as principais técnicas do IRAMUTEQ:

| Técnica | O que produz | Arquivo |
|---|---|---|
| **Frequência lexical** | Ranking de palavras globais e por mês | `frequencia_global.csv` e `frequencia_por_periodo.csv` |
| **Especificidade por período** | Palavras sobre/sub-representadas em cada mês (qui-quadrado) | `especificidade.csv` |
| **Co-ocorrência / similaridade** | Pares de termos que aparecem juntos e grafo de similaridade | `coocorrencia.csv` e `grafo_similaridade.json` |
| **AFC (Análise Fatorial de Correspondências)** | Mapa fatorial palavra × período (eixos 1–2) | `afc_coordenadas.csv` |
| **CHD (Classificação Hierárquica Descendente)** | Segmentação do corpus em classes temáticas (Ward) com palavras características (chi2) | `chd_classes.csv` |

### Como gerar
```powershell
cd backend
python scripts/analise_lexical.py                     # gera tudo em data/export/lexical/
python scripts/analise_lexical.py --n-classes 6      # ajusta o nº de classes da CHD
```

A saída alimenta o dashboard (nuvem de palavras já integrada) e pode ser usada em
relatórios e análises de pauta, temas por período e enquadramento da mídia.

## 13. Benchmarking — Ferramenta DSM (Dinâmica MT)

Referência para a **Fase 2** (sprints 21–27 em `implementation.md`): a ferramenta
de clipping/análise de mídia da DSM (`https://dsm.dinamicamt.com.br`) foi mapeada por
engenharia reversa (login real + captura de UI/rotas) em 20/08/2026. O objetivo é levar
o ValorPúblico ao mesmo nível funcional, somando às funcionalidades já existentes.

### Funcionalidades observadas na DSM

- **Dashboard (Início):** filtros de período (Hoje / 7d / 30d / Personalizado) e categorias;
  KPIs de avaliações e menções (positivas/neutras/negativas); veículos monitorados por tipo
  (WEB 15.117, RÁDIO 806, TV 127, IMPRESSO 19, REVISTAS 7); insights principais (maior
  cobertura, veículo em destaque, tendência positiva); Top Veículos com filtro por tipo;
  volume de notícias semanal; análise de sentimento (donut %) e notícias recentes.
- **Relatórios (Pesquisa avançada):** filtros por período, estado, município, avaliação,
  avaliação IA, tipo de veículo, veículo, categorias e termos; lista de notícias (veículo,
  editoria, tipo, categorias, avaliação) com caixa de seleção; **somatório de espaço** por tipo
  (site=caracteres, rádio=tempo, TV=tempo, impresso=cm²), **somatório de valor (R$)** e
  **somatório de sentimento**.
- **Análise de Mídia:** abas Estatística / Qualitativa / Repercussão Negativa; filtros de
  data e assuntos; **Exportar PDF**.
- **Detalhe de notícia:** valoração detalhada (R$ calculado, valor do veículo, base de
  valoração), categorias (agentes/temas), conteúdo integral e palavras-chave.
- **Painel do cliente:** busca por título/categoria/estado e navegação por categorias de mídia.
- **Redes sociais:** ainda em desenvolvimento na DSM (solicitação de acesso antecipado).

### Lacunas (o que a DSM tem e o ValorPúblico ainda não)

| Funcionalidade DSM | Status no ValorPúblico |
|---|---|
| Filtros de período (Hoje/7d/30d/Personalizado) nos KPIs/séries | A implementar (Sprint 21) |
| Insights Principais e Top Veículos por tipo | A implementar (Sprint 22) |
| Categorias/temas por notícia | A implementar (Sprint 23) |
| Detalhe de notícia (valoração, categorias, palavras-chave) | A implementar (Sprint 24) |
| Pesquisa avançada/relatórios com somatórios (espaço/valor/sentimento) | A implementar (Sprint 25) |
| Análise de Mídia (estatística/qualitativa/repercussão negativa) | A implementar (Sprint 26) |
| Exportação PDF de relatório | A implementar (Sprint 27) |

O que **já temos** e supera/iguala a DSM: valoração R$ por veículo/CPM, share de mídia
destrincado (Portal/Rádio/TV/Jornal/Governo/Redes/YouTube), nuvem de palavras com filtro
mensal, série temporal por sentimento, análises lexicais IRAMUTEQ (frequência, especificidade,
co-ocorrência, AFC, CHD) e exportação CSV de auditoria.