# Camada DSM — o que mudou no produto e por quê

Documento de referência da camada de inteligência adicionada aos dois painéis
(**Assessor Público** e **Valor Público**) a partir do estudo de mercado
realizado em 23/11/2026 (agências de clipping como Dinâmica Clipping/DSM,
Knewin, SimpliNG/SMI, Sinopress, Interclip, CWA, Preview News) e das regras
legais da Lei 9.504/1997 (Lei das Eleições).

> Princípio: **o que não é explicitado pelo cliente não é entregue.** Cada item
> abaixo tem regra, métrica e fonte — nenhum campo é "decorativo".

---

## 1. O gap que a Camada DSM fecha

| Lacuna de mercado (o que o cliente pergunta) | Antes | Agora (Camada DSM) |
|---|---|---|
| "A menção é direta ou indireta?" | só contagem | `tipo_mencao`: direta / indireta / indeterminada, com **papel** (protagonista, porta-voz, citada) e **porta-vozes** identificados |
| "Qual foi o trecho exato?" | texto inteiro | `trecho` com recorte por frase + offsets + destaque de palavras-chave (`<mark>`) |
| "Isso é problema ou só menção?" | sentimento cru | `alertas` acionáveis: negativa direta, alto valor, tier-1 negativo, compliance, tema novo, falha de coleta |
| "A campanha estáregular?" | não existia | `compliance_eleitoral`: motor da Lei 9.504/1997 (arts. 39, 39-A, 40, 45, 49, 53, 55, 56, 57-A e impulsionamento) |
| "Quem veicula propaganda pública?" | não existia | `radar de propaganda pública`: separa matéria jornalística de publicidade institucional/oficial/utilidade pública, com órgão, tipo e símbolos públicos |
| "Quanto tempo leva para eu saber?" | não existia | `cobertura`: SLA médio/p95 entre publicação e disponibilidade, cobertura por veículo/tier e **veículos ausentes** |
| "Quanto vale em cm² / AVPE?" | valor de mercado solto | `valor_avpe`: centimetragem (cm² × R$/cm²), R$/minuto para TV/rádio, AVPE qualificada |
| "Quero receber isso no WhatsApp" | inexistente | `newsletter` consolidada em HTML (e-mail/PDF) + texto pronto para WhatsApp/Telegram, com webhook de entrega |

---

## 2. Módulos novos (backend)

### 2.1 `processing/mencao.py` — menção direta/indireta/indeterminada
Classificação **por regras, sem LLM** (rápida, gratuita, auditável):
1. termo monitorado + sinal de citação ("disse", "afirmou", "segundo") ou presença no título → **direta**;
2. presença em contexto genérico/agregado ("boletim", "levantamento") → **indeterminada**;
3. demais casos → **indireta**.
Papel: `protagonista` (título ou recorrência), `porta-voz` (pessoa citada com cargo), `citada`.
Cada resultado guarda `motivos[]` — o painel explica **por que** classificou.

### 2.2 `processing/trecho.py` — recorte + destaque
Quebra em frases, pontua por densidade de termos, devolve o trecho mais
relevante com offsets (`inicio`/`fim`, úteis para abrir em seeks no áudio/vídeo)
e `destacar()` gera HTML com `<mark>`.

### 2.3 `processing/compliance_eleitoral.py` — motor da Lei 9.504/1997
Regras implementadas (texto oficial conferido):

| Artigo | Regra | Efeito no painel |
|---|---|---|
| 39 | Ato de propaganda em recinto não exige licença, mas **comunicação com 24 h** | alerta de atenção até 7 dias antes da eleição |
| 39-A | No dia da eleição só **manifestação individual e silenciosa** | alerta crítico se houver material/ato (bandeira, adesivo, comício) |
| 40 | **Crime**: usar símbolo/frase/imagem de órgão público em propaganda | alerta crítico (com base legal anexa) |
| 45 | Emissoras: vedado pesquisa identificável, trucagem degradante, propaganda no noticiário | atenção em clipping de rádio/TV com pesquisa |
| 49 | 2º turno: rádio 7h/12h, TV 13h/20h30 (blocos de 10 min) | informação de conferência de veiculação |
| 53 | Sem cortes instantâneos/censura prévia; vedado degradar candidato | atenção a termos de degradação |
| 55/56 | Perda de tempo (dobro) e suspensão de emissora (24 h) | contexto de risco |
| 57-A | Propaganda na internet só após **15 de agosto** | alerta crítico para conteúdo de campanha antes da data |
| Art. 26 | Impulsionamento é gasto eleitoral sujeito a prestação de contas | informação para prestação de contas |

Calendário configurável por `settings.py` (`ELEICAO_ANO`, `ELEICAO_1O_TURNO`,
`ELEICAO_2O_TURNO`); padrão 2026 (1º turno 04/10, 2º turno 25/10) e 2024
municipal (06/10 e 27/10).

### 2.4 `processing/propaganda_publica.py` — radar
Classifica cada clipping como `propaganda_publica` (institucional, utilidade
pública, oficial, licitação, publicidade) ou `materia_journalistica`, identifica
o **órgão** (câmara, prefeitura, governo, tribunal, órgão federal) e marca
uso de **símbolos públicos** (base do art. 40).

### 2.5 `processing/alertas.py` — alertas acionáveis
Regras: `NEGATIVA_DIRETA` (crítico), `TIER1_NEGATIVA` (crítico), `VALOR_ALTO`
(alto), `COMPLIANCE` (crítico), `RADAR` (info), `TEMA_NOVO` (info),
`SEM_FONTE` (atenção, qualidade da coleta). Cada alerta tem `chave`
(deduplicação), `acao_sugerida` e link da fonte.

### 2.6 `processing/cobertura.py` — SLA e qualidade do monitoramento
- `sla_min_medio`, `sla_min_p95`, `sla_min_mediano` (publicação → disponibilidade);
- `pct_cobertura`, `com_veiculo`, `sem_data_publicacao` (falha de extração);
- `por_veiculo` com tier (Tier 1/2/3) e SLA por veículo;
- `veiculos_ausentes` (contrato de cobertura auditado).

### 2.7 `processing/enriquecimento.py` — cola de tudo
Aplica os módulos acima a um clipping e devolve os campos graváveis.
Usado no **orquestrador** (coleta nova) e no **backfill** (clippings antigos).

### 2.8 `processing/valoracao.py` — AVPE e centimetragem
Mantém o valor de mercado (`valor_estimado`) e soma:
`valor_avpe` (impresso: cm² × R$/cm²; TV/rádio: duração × R$/minuto),
`espaco_cm2` e `duracao_seg`. As bases vivem em `tabela_midia/geral`
(`bases_valoracao`), editáveis no seed `seed_tabela_midia.py`.

### 2.9 `scraper/propaganda_publica_scraper.py` — coleta do radar
Fontes oficiais configuráveis em `FONTES_PROPAGANDA_PUBLICA` (padrão: lista curada
em `backend/config/fontes_radar.py`), com extração em quatro camadas — a
primeira que devolver itens vence:
1. **RSS/Atom** (feedparser) — ex.: Prefeitura de Várzea Grande (`/feed`);
2. **Links de conteúdo** (`<a>` cujo href casa com `/noticias/`, `/conteudo/`,
   `publicacoes_ver_conteudo/`) — traz a URL do ato;
3. **Texto principal** (trafilatura) — ex.: Prefeitura de Cuiabá (`/noticias`);
4. **Títulos** (`h1..h5`) — ex.: Secom-MT, Câmara de Cuiabá.

Filtros de ruído: páginas de erro/WAF ("the requested URL was rejected",
403/404) e títulos que são apenas datas. Páginas acima de 8 MB são ignoradas
(o feed oficial cobre o mesmo conteúdo). O órgão emissor é deduzido do texto e,
na falta, do domínio (`ORGAO_POR_DOMINIO`).

### 2.10 `config/fontes_radar.py` + `scripts/ingerir_radar.py` — o plug das fontes
Lista curada **verificada** (HTTP 200 + conteúdo extraível, testada em
23/11/2026):

| Entidade | Fontes |
|---|---|
| **Cuiabá** | `www.cuiaba.mt.gov.br/noticias` · `www.cuiaba.mt.gov.br/` · `www.camaracuiaba.mt.gov.br/` |
| **Várzea Grande** | `www.varzeagrande.mt.gov.br/feed` (RSS oficial) · `/transparencia` · `/diario-oficial` |
| **ALMT / Estado de MT** | `www.iomat.mt.gov.br/clipping` (IOnews — clipping oficial do DOE-MT) · `www.iomat.mt.gov.br/` (publicações do diário) · `www.secom.mt.gov.br/inicio` (propaganda institucional do Estado) · `www.secom.mt.gov.br/noticias` · `www.cge.mt.gov.br/noticias` · `www.transparencia.mt.gov.br/` |

`ingerir_radar.py` grava em `radar_publico` (coleção privada — só o backend
lê) e `atualizar_radares.py` soma esses itens ao escopo **geral** e ao escopo
da cidade correspondente (Cuiabá / Várzea Grande).

> **ALMT:** o domínio institucional da Assembleia **não resolve publicamente**
> (NXDOMAIN confirmado em 23/11/2026 para `almt.leg.br`, `assembleia.mt.gov.br`
> e `almt.mt.gov.br`, via resolvedores público e DoH). Por isso o radar usa os
> canais oficiais que a Assembleia utiliza — o **DOE-MT (IOnews)**, onde são
> publicados os atos do Estado, e a **Secom-MT**, que veicula a agenda
> institucional. Basta acrescentar o domínio correto em
> `FONTES_PROPAGANDA_PUBLICA` quando ele for divulgado.

### 2.11 `scripts/ingerir_radar.py` — saída
Grava cada item com `classe = publicacao_oficial` (é publicação de canal
ofICIAL, mesmo que o texto não se pareça com propaganda), mantendo a
classificação semântica em `classe_semantica` (`propaganda_publica`,
`materia_journalistica`), além de `orgao`, `tipo`, `simbolos_publicos` e
`cidade`.

---

## 3. Scripts novos

| Script | O que faz | Quando roda |
|---|---|---|
| `scripts/enriquecer_clippings.py` | backfill de menção/trecho/compliance/radar nos clippings já gravados | após a ingestão |
| `scripts/atualizar_radares.py` | publica `radares/`, `alertas/` e `cobertura/` (escopos `geral`, `cidade-*`, `agente-*`; janelas hoje/7d/15d/30d) | após as métricas |
| `scripts/gerar_newsletter.py` | gera a newsletter consolidada (HTML + texto WhatsApp) em `newsletters/`; `--enviar` dispara o `NEWSLETTER_WEBHOOK` | fim da rotina |

Ordem na rotina (`rotina_diaria.ps1` e `.github/workflows/ingestao.yml`):
`run_ingestao` → `atualizar_metricas` → `analise_lexical_escopos` →
`gerar_release_ia` → **`enriquecer_clippings`** → **`atualizar_radares`** →
**`gerar_newsletter`**.

---

## 4. Painéis novos (frontend)

Seção **"Camada DSM — Radar, Alertas, Menções e Cobertura"** (`frontend/js/dsm.js`):

1. **Radar de propaganda pública** — resumo (publicações, % do clipping, valor,
   com símbolos) + tabela (publicação, órgão, tipo, valor, símbolo público, link).
2. **Alertas acionáveis** — feed com nível, título, detalhe, fonte, data, valor e
   **ação sugerida**.
3. **Menções e porta-vozes** — donut direta/indireta/indeterminada + chips dos
   porta-vozes mais citados.
4. **Cobertura e SLA** — SLA médio/p95, % de cobertura, veículos coletados,
   itens sem data e **veículos esperados sem coleta**.
5. **Botões Newsletter / Copiar texto** — abrem o HTML gerado ou copiam o texto
   pronto para o WhatsApp.

As coleções novas exigem `match` explícito em `firestore.rules` (o catch-all
nega tudo) — já incluído.

---

## 5. Novas variáveis de ambiente

```
FONTES_PROPAGANDA_PUBLICA=            # URLs separadas por vírgula
HABILITAR_PROPAGANDA_PUBLICA=0
PROPAGANDA_PUBLICA_MAX_ITENS=20
TIER1_VEICULOS=                       # veículos de alto impacto
VEICULOS_ESPERADOS=                   # compromisso de cobertura (contrato)
ALERTA_VALOR_ALTO=1500
COMPLIANCE_ELEITORAL_ENABLED=1
ELEICAO_ANO=2026
ELEICAO_1O_TURNO= / ELEICAO_2O_TURNO=
NEWSLETTER_ENABLED=1
NEWSLETTER_WEBHOOK=                   # Make/Zapier/n8n -> e-mail/WhatsApp
NEWSLETTER_MAX_ITENS=15
NEWSLETTER_ASSINATURA=
```

---

## 6. Regras de qualidade (o que não pode quebrar)

1. **Determinismo**: classificação por regras; a IA continua só no release
   executivo. Nenhum painel depende de LLM para funcionar.
2. **Auditoria**: toda classificação guarda `motivos[]`; o clipping bruto
   permanece inacessível ao cliente, mas o painel mostra a fonte.
3. **Sem dado inventado**: se a coleta falhou, o painel mostra "sem data" e
   "veículo sem coleta" — falha visível, não número inventado.
4. **Base legal sempre anexada**: alerta de compliance carrega o artigo.
5. **Idempotência**: backfill e publicação podem rodar várias vezes por dia.
6. **Escopo duplo**: a Camada DSM roda para `geral`, por cidade e por agente —
   mesma regra, três leituras.

---

## 7. Referência

- Estudo de mercado e fontes: `D:\Dev\DarkAI\dinamicaclipping\pesquisa\`
  (`01_GUIA_CLIPPING_COMPLETO.md`, `02_DINAMICA_DSM_SERVICOS_E_FEATURES.md`,
  `03_MERCADO_CONCORRENTES.md`, `04_CONTRATO_CHECKLIST_E_RFP.md`,
  `06_REGRAS_DE_NEGOCIO.md`).
- Texto oficial da Lei 9.504/1997 (Planalto) foi conferido antes de codificar
  as regras de compliance.

---

## 8. Entrega, acesso e visualização (nov/2026)

### 8.1 Entrega de alertas (`scripts/enviar_alertas.py`)
Fecha o gap de "alerta que morre no painel":
- lê `alertas/<escopo>`, filtra por **nível mínimo** (`ALERTA_NIVEL_MINIMO`) e janela;
- **deduplica** pelo `chave` do alerta no estado `alertas_enviados/estado`;
- envia por **SMTP** (e-mail, sem dependência externa) e/ou **webhook**
  (`ALERTA_WEBHOOK_URL` — Make/Zapier/n8n → WhatsApp/Telegram/Slack);
- `--dry-run` lista o que seria enviado; `--forcar` reenvia.

### 8.2 Métricas da Camada DSM no agregado
`metricas/geral`, `metricas_por_cidade/*` e `metricas_por_agente/*` passam a trazer:
`valor_avpe_total`, `valor_avpe_por_plataforma`, `distribuicao_mencoes`,
`distribuicao_papeis`, `porta_vozes`, `compliance` (artigos/níveis),
`radar` (total/órgãos/símbolos), `alertas` (níveis/tipos) e `cobertura`
(SLA médio/p95, % de cobertura). O escopo geral e o de cidade trazem
**`share_of_voice`** (ranking de agentes por menções, share %, tom e valor).

### 8.3 Dashboard
- **4 KPIs da Camada DSM** no topo: menções diretas (%), alertas críticos,
  SLA de coleta e valor AVPE (com nota de % sobre o valor de mercado).
- **Painel "Share of Voice — espaço de mídia por agente"** (gráfico + tabela
  com posição, menções, share, positivo e negativo).

### 8.4 Acesso individual (RBAC)
- `frontend/js/auth.js`: login/logout por e-mail e senha (Firebase Auth),
  leitura do perfil em `usuarios/{uid}` e aplicação do escopo nos filtros.
- `firestore.rules`: modo de acesso via `config_acesso/publico`
  (`true` = painel aberto; `false` = exige login).
  No modo restrito, cada usuário só lê o **próprio escopo**
  (`metricas_por_agente/<id>`, `alertas/agente-<id>`, `radares`, `cobertura`,
  `newsletters`, `releases_ia`, `analise_lexical`); `geral` fica para quem tem perfil.
- `scripts/seed_acesso.py` cria/ajusta o modo (público ou restrito).

### 8.5 PDF, CSV e release
- **PDF** (`gerar_relatorio_pdf.py`): novas seções de **menções**, **papéis**,
  **porta-vozes**, **compliance**, **radar**, **alertas**, **cobertura/SLA**,
  **AVPE** e **share of voice**; branding parametrizado (`APP_NOME`/`--app`).
- **CSV** (`exportar_clippings.py`): colunas `tipo_mencao`, `papel_mencao`,
  `porta_vozes`, `trecho_citado`, `compliance_*`, `radar_*`, `simbolos_publicos`,
  `valor_avpe`, `espaco_cm2`, `duracao_seg`.
- **`exportar_camada_dsm.py`**: CSV de auditoria de `radar_publico`, `alertas` e `cobertura`.
- **Release de IA**: o contexto enviado ao modelo agora inclui menções, papéis,
  porta-vozes, compliance (com artigo), radar, alertas e AVPE; o prompt orienta
  o modelo a usar cada bloco.

### 8.6 Operação e robustez
- Rotina diária: `ingerir_radar` → `enriquecer_clippings` → `atualizar_radares`
  → `enviar_alertas` → `gerar_newsletter`.
- **Escrita em lote** no backfill (400 docs/lote) + retry com backoff.
- **Cota do Firestore**: `core/quota.py` converte `429/ResourceExhausted` em
  saída limpa com código **75** (EX_TEMPFAIL); o workflow trata 75 como aviso e
  repete no ciclo seguinte (não abre issue de falha).
- CI roda os **testes** (Camada DSM + regras do Firestore no emulador) antes da
  ingestão, e há workflow manual de deploy do Hosting.

## Redes sociais via buscador (LGPD)

A coleta de redes sociais consulta um buscador publico (SearXNG em container
proprio, depois DuckDuckGo/`ddgs` como reserva) com `site:` por rede e guarda
o que a propria pagina de resultados ja exibe publicamente: titulo,
descricao/snippet, URL, data (quando o snippet indica) e eventual trecho de
comentario publicado.

- **Decisao do dono (24/11/2026):** coleta por navegador com stealth
  (`NAVEGADOR_STEALTH`, on nos dois apps) e a **conta logada do proprio agente**
  estao liberadas; tambem pode-se coletar e exibir nome/usuario, foto e rosto
  de terceiros. As salvaguardas do `plano/19` §3.1 valem (ritmo, limite
  diario, log, desligamento imediato em bloqueio).
- Base legal e finalidade ficam registradas: monitoramento de imagem publica e
  atendimento do mandato, com retencao definida e canal de exclusao a pedido.
  **Continua proibido** montar ficha individual de cidadao ou lista de
  opositores; o pipeline trata comentaristas como tema/sentimento agregados.
- Os clippings brutos (incluindo os de redes) continuam **privados**: o cliente
  le apenas o agregado `redes_sociais` em `metricas*` (por rede, sentimento por
  rede, total de comentarios e ate 40 itens recentes com snippet e link).
- Itens com `confianca = "baixa"` (nome do agente so no titulo) **nao** geram
  alertas.
- Orcamento por execucao (`BUSCA_SOCIAL_MAX_CONSULTAS`) com rodizio de metade
  dos agentes por dia e dedup por URL.
