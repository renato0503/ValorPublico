# ValorPúblico — Contexto Estratégico

> Documento vivo de contexto da plataforma de **Business Intelligence (BI)** e
> **Monitoramento de Mídia** focada em inteligência política e institucional.
> Atualizado em: 19/08/2026 (fim do dia de trabalho).

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

## 2. Público-Alvo

| Segmento | Necessidade principal |
|---|---|
| **Pré-candidatos e candidatos** | Posicionamento, prova de volume de mídia, análise de concorrência |
| **Vereadores e mandatos ativos** | Prestação de contas, medição de engajamento, imagem pública |
| **Assessores de comunicação / marketing político** | Relatórios de clipagem, valoração de mídia espontânea |
| **Partidos e institutos de pesquisa** | Cruzamento de sentimento com intenção de voto |
| **Consultorias políticas** | Inteligência competitiva e recomendações de pauta |

**Escopo geográfico inicial:** Mato Grosso — municípios de **Cuiabá** e **Várzea Grande**.

## 3. Escopo de Dados (Alvos Monitorados)

- **50 parlamentares municipais**:
  - **Cuiabá (MT):** 27 vereadores.
  - **Várzea Grande (MT):** 23 vereadores.
- Cada alvo é cadastrado como um **agente público** com variações de nome
  (`termos_de_busca`) usadas para varrer mídia e redes sociais.

### Fontes monitoradas
- **Mídia tradicional:** Web / portais de notícias (via Google News RSS + Trafilatura).
- **Redes sociais:** Twitter/X, Instagram, Facebook, YouTube, Telegram.
- **Coberturas futuras:** TV, Rádio e Impresso (valoração e transcrição de falas).

## 4. Arquitetura Tecnológica

```
┌─────────────────────────────┐        ┌─────────────────────────────┐
│       BACKEND (Python)      │        │   FRONTEND (PWA / JS)       │
│  Motor de ingestão/scraping │        │   Dashboard de BI           │
│  Pipeline NLP de sentimento │        │   Filtros + KPIs + gráficos  │
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
- **Paralelismo:** scrapers assíncronos via `asyncio` + scrapers síncronos via
  `ThreadPoolExecutor` (orquestrados pelo `Orchestrator`).
- **Processamento:** `pandas` para limpeza/deduplicação; NLP de sentimento via
  VADER expandido com léxico em português (positivo/negativo/neutro).

### Scrapers implementados (conforme pesquisa 2026)
| Plataforma | Ferramenta | Observações |
|---|---|---|
| Twitter/X | `twscrape` | Exige cookies reais (`auth_token`, `ct0`); pool de contas SQLite + rotação em HTTP 429 |
| Instagram | `instaloader` | Sessão/cookies injetados; limite conservador p/ evitar ban por IP |
| Facebook | `Playwright` + stealth | `facebook-scraper` está morto desde 2022; exige cookies de navegador e rolagem humana |
| YouTube | `yt-dlp` + `youtube-transcript-api` | Metadados + comentários + transcrição das falas (rica p/ sentimento) |
| Telegram | `Telethon` (MTProto) | Nunca usar clones do Pyrogram (Operação Navy Ghost) |
| Web/Notícias | Google News RSS + `Trafilatura` | Extração de texto limpo (boilerplate removido), pronto p/ RAG |

### Frontend (PWA)
- **Stack:** HTML5 + CSS3 + JavaScript (módulos ES6), Firebase JS SDK, Chart.js.
- **Recursos PWA:** `manifest.json`, Service Worker (offline-first), instalação.
- **Dashboard:** KPIs executivos, série temporal de menções, share de mídia,
  ranking Top 10 fontes, análise de sentimento e filtros por cidade/parlamentar.

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
| `plataforma` | string | Twitter, Instagram, Facebook, Web, YouTube, Telegram |
| `tipo` | string | Postagem, Comentário, Notícia |
| `texto_limpo` | string | Texto normalizado (limpo p/ NLP) |
| `sentimento` | string | positivo / negativo / neutro |
| `data_publicacao` | timestamp | Data da publicação |
| `autor` / `url` / `alcance` / `valor_estimado` | — | Metadados de fonte e audiência |

### Coleções de métricas (otimizadas para o dashboard em tempo real)
- `metricas/geral` — KPIs globais.
- `metricas_por_cidade/<slug>` — visão por cidade.
- `metricas_por_agente/<id>` — visão por parlamentar.
- `metricas_diarias/serie` — série temporal por dia/plataforma.
- `usuarios/{uid}` — controle de acesso (papel `owner`, etc.).

## 6. Regras de Negócio

1. Cada clipping pertence a **um agente** (via subcoleção) e a **uma plataforma**.
2. `termos_de_busca` são gerados automaticamente combinando nome, cargo (flexão
   por gênero) e partido, em versões com e sem acento (máx. de match).
3. Todo texto passa por **limpeza** (remoção de URL/emoji/boilerplate) e
   **deduplicação** antes de entrar no Firestore.
4. O **sentimento** é classificado antes da persistência (VADER + léxico PT).
5. Métricas agregadas são **recalculadas** por script (não lidas no cliente),
   garantindo alta performance e leitura leve em tempo real.
6. **Segurança:** credenciais e chaves de serviço ficam **fora do git**
   (`.env`, `serviceAccountKey.json`, `firebase-config.js`).

## 7. KPIs do Dashboard

- Total de **veículos/fontes** monitoradas.
- **Audiência total** estimada (soma de alcance).
- **Valoração total** (R$) da mídia espontânea.
- Total de **clippings**.
- **Série temporal** de menções por dia.
- **Share de mídia** (Web, Redes Sociais, YouTube, Telegram, etc.).
- **Análise de sentimento** (positivo/neutro/negativo).
- **Top 10** veículos/páginas mais relevantes.

## 8. Estrutura de Pastas

```
ValorPublico/
├── backend/
│   ├── config/settings.py          # env + configuração
│   ├── core/                       # firebase_client, logger
│   ├── scraper/                    # scrapers + orchestrator + models
│   ├── processing/                 # cleaner (pandas) + sentiment (VADER PT)
│   ├── storage/                    # firestore_repo
│   ├── scripts/                    # seed, ingestão, métricas, owner
│   ├── data/                       # seeds / raw / processed (gitignored em parte)
│   ├── requirements.txt
│   └── .env.example                # template de configuração
├── frontend/                       # PWA (index.html, manifest, sw, css, js)
├── context.md                      # este documento
└── .gitignore
```

## 9. Segurança e Boas Práticas

- Nunca versionar: `.env`, `*.json` de chaves, `serviceAccountKey*`,
  `firebase-config.js`, cookies/sessões, proxies.
- Antes de qualquer commit: revisar `git diff --cached` e varrer segredos.
- **Rotacionar chaves** de conta de serviço caso sejam expostas.
- Para escala real de scraping, usar **proxies residenciais/móveis** (o código
  já suporta `PROXY_LIST`).

## 10. Estado Atual (19/08/2026)

- **Banco (Firestore):** foi zerado e repopulado do zero.
  - ✅ `agentes_publicos` — 50 agentes (27 Cuiabá + 23 Várzea Grande), com `votos_2024`, `legislatura` e `termos_de_busca`.
  - ✅ `tabela_midia/geral` — CPM de 6 plataformas + 10 veículos (valoração).
  - ⚠️ `clippings` — 420 clippings gravados (ingestão Web em andamento, interrompida no 13º agente; retomar em lote).
  - ⚠️ `metricas` — **ainda não recalculadas** (rodar `atualizar_metricas.py` após completar a ingestão).
  - ❌ `usuarios` — owner foi apagado no reset (recriar com `criar_owner.py`).
- **Frontend (PWA):** deployado em `https://valorpublico.web.app`.
  - ✅ Config do Firebase **embutida** no `js/firebase-init.js` (eliminou o erro de MIME do `firebase-config.js`).
  - ✅ Layout refatorado (dark mode executivo, grid assimétrico, KPIs com tendência, donut de sentimento).
  - ⚠️ Se ainda exibir erro de MIME no navegador: fazer **hard refresh (Ctrl+Shift+R)** ou **limpar cache do site** (DevTools → Application → Clear storage) para o service worker v3 assumir.

## 11. Próximos Passos (para continuar amanhã)

- [ ] **Completar a ingestão Web** — rodar `run_ingestao.py` (Web) até os 50 agentes (persistência incremental já salvou 13).
- [ ] **Rodar `atualizar_metricas.py`** — regenerar `metricas/geral`, `metricas_por_cidade`, `metricas_por_agente`.
- [ ] **Recriar o owner** — rodar `criar_owner.py` (foi apagado no reset).
- [ ] **Validar o dashboard** em `https://valorpublico.web.app` com os dados reais.
- [ ] **Ativar YouTube/Telegram** — diversificar share de mídia e gerar audiência (alcance).
- [ ] **Redes sociais** — configurar credenciais (Twitter cookies, Instagram sessão, Facebook Playwright).
- [ ] **Agendamento da ingestão** — Cloud Scheduler / cron.
- [ ] **Regras de Firestore Security (RBAC)** — proteger coleções por papel.
- [ ] **Cobertura TV, Rádio e Impresso** — transcrição de falas e valoração específica.
