# HANDOFF — Valor Público

> **Atualização 26/11/2026 (tarde):** três entregas no ar — (1) **vazamento corrigido**: `impressao.css` era carregado com `media="print"`, então o `.print-only` nunca era aplicado na tela e o cabeçalho/rodapé de impressão aparecia em **todas** as telas; (2) **fontes do discurso**: o front esperava objetos e o backend publica texto (`"Veículo, 2026-11-24"`), por isso a lista mostrava “Fonte” repetido — agora é o botão **“Fontes (N)”** com veículo, data e link da matéria; (3) **simulador do próprio discurso** (tela `#/personas`): o usuário cola o texto e as 12 personas reagem de uma vez (aderência, risco, o que funciona, o que incomoda e o que reescrever), com endpoint novo `POST /v1/discurso/simular` no Cloud Run (timeout 300 s). Também: botão `?` explicando a geração do discurso (D-01) e a simulação (D-02), e a aba “Simulação” saiu da barra da tela Semana. Publicação: Hosting `valorpublico-v55`, Cloud Run `personas-api-00002-mqt`. Commit `1604e54` enviado. **Pendência:** teste ponta a ponta do simulador com usuário logado.

> **Atualização 26/11/2026 (noite):** os **PDFs profissionais em A4** foram concluídos e testados (`frontend/js/documentos.js`, `frontend/css/documento.css`, `frontend/tests/validar_pdfs.py`): os 8 botões de PDF (executivo, governo, clipping, redes, semana, governador, tendências, personas) montam documentos próprios com capa, sumário, seções numeradas, KPIs, gráficos, tabelas e "Página X de Y". Regressão: `validar_cliente.py` 18 telas/22 ações/0 falhas/0 overflow e `teste_clipping_governo.mjs` 0 falhas. Ver `../plano/22_SPRINTS_PROMESSAS_APRESENTACAO.md` §8.


> Continuidade do app. Documento master do projeto: **`D:\Dev\CerraClipping\STATUS_PROJETO.md`**.
> Atualizado em 23/11/2026.

---

## 1. Onde paramos

O ValorPublico está em produção (`valorpublico.web.app`) com **identidade própria**
("Newsroom", claro/escuro), **modo restrito**, 6 telas por rota e regras publicadas.

### 1.1 Base

| Commit | Entrega |
|---|---|
| `9272640` | **Camada DSM** — menção, trecho, compliance eleitoral, radar de propaganda pública, alertas, cobertura/SLA, AVPE, newsletter, painel `dsm.js`, regras. Inclui o **`frontend/index.html` reconstruído** (estava truncado em 17 bytes na working tree). |
| `93fa3ba` | **Completude** — entrega de alertas (SMTP/webhook), RBAC por agente, share of voice, PDF/CSV completos, testes + CI |

### 1.2 Sessão de 23/11

| Commit | Entrega |
|---|---|
| `ffb25e3` | Repõe `core/quota.py`, trava de projeto e caminho relativo da chave |
| `d8ec582` | `main_com_cota` importado em `atualizar_metricas`/`exportar_clippings` |
| `b0930f5` | Sanitização NaT/NaN no Firestore e `criar_usuario.py` |
| `02d755a` | Layout responsivo + motion 3D (transições, splash) |
| `d1e965c` | Docs de layout/motion |
| `67a4925` | **Identidade "Newsroom"**: masthead, 6 telas por rota, login em página inteira, marca/ícones próprios; regras publicadas |
| `96a3be4` | Tema "Edição da noite", "Esqueci minha senha" e templates de e-mail |
| `4663802` | Admin lê qualquer escopo; gráficos com valores/cores; diagnóstico no console |

**Validado no fim da sessão:** DSM 23/23 · guarda 4/4 · imports 3/3 · sanitize 10/10 ·
rules 30/30 · login gate · 6 rotas · temas claro/escuro · 8 gráficos · sem overflow ·
filtro por agente sem `permission-denied` · produção sem erros de JS.

---

### 1.3 Sessão 23/11 (noite) — tema, ALMT e redes sociais

| Commit | Entrega |
|---|---|
| `d473d9d` | **A** contraste AA (tokens Newsroom/Edição da noite; capa do login legível; banner mobile sem 404); `contraste.py` 0 violações |
| `18ed375` | **C** 24 deputados ALMT (seed, radar, “Parlamentares por casa”) |
| `167e603` | **B** redes sociais via buscador; seção na tela Mídia; `redes_almt.yml` (cron **desativado**); `redes_sociais` nas métricas |

Estado: **74 agentes** (`count()`=74). O workflow `redes_almt.yml` (run **45283321859**, success)
coletou **130 clippings sociais** dos 24 deputados e recalculou: **7.353 clippings, 74 no SoV,
74 `metricas_por_agente`**, `redes_sociais` = `{Instagram 47, Facebook 26, Twitter 10, TikTok 6}`
(5 comentários, 40 recentes) em `metricas/geral` e `mato-grosso`. O secret
`FIREBASE_SERVICE_ACCOUNT_B64` estava com a chave revogada e foi atualizado; o **cron do
`redes_almt.yml` está ativo** (06:00 Cuiabá). Push e deploy do Hosting feitos em 23/11.

## 2. Diferenças em relação ao Assessor Público

| Item | ValorPublico | AssessorPublico |
|---|---|---|
| Projeto Firebase | `valorpublico-b1e6d` | `assessorpublico` |
| Release de IA | **não tem** (removido de propósito) | tem (`releases_ia`) |
| SDK do Firebase no front | `importmap` (`10.12.2`) | URL `gstatic/9.22.0` |
| Janelas de período | hoje / 7d / 30d | hoje / 7d / 15d / 30d |
| Dados | migrados para o projeto do Assessor Público (2026) | ativo |

> **Recomendação:** se o ValorPublico não for mais comercializado, descontinuá-lo e manter
> apenas o Assessor Público (evita dois pipelines e dois bancos).

---

## 3. Estado dos dados (projeto `valorpublico-b1e6d`)

- **O pipeline não roda neste projeto desde a migração de dados** para `assessorpublico`.
- ⚠️ **Correção (23/11):** ao contrário do que este documento dizia, `radar_publico` (29),
  `radares`, `alertas` e `cobertura` (53 cada) **existem aqui** — foram gravados pelo backfill
  de 23/11, que usou por engano a chave deste projeto (achado A1). É lixo operacional:
  não apagar sem antes decidir o destino (§4).

## 3.1 Correções de infraestrutura aplicadas (23/11)

- `backend/core/quota.py` reposto (estava ausente e quebrava 6 scripts — achado A4).
- `backend/core/firebase_client.py` com a mesma trava do app principal: aborta se o
  `project_id` da chave divergir de `FIREBASE_PROJECT_ID` (aqui, `valorpublico-b1e6d`).
  Teste: `python tests/teste_firebase_guard.py` (4/4).
- `FIREBASE_SERVICE_ACCOUNT` aceita caminho relativo a `backend/` (padrão `serviceAccountKey.json`).

Para operar o ValorPublico como app independente:

```powershell
cd D:\Dev\CerraClipping\ValorPublico\backend
# .env já aponta para serviceAccountKey.json (relativo a backend/)

python scripts/run_ingestao.py
python scripts/atualizar_metricas.py
python scripts/ingerir_radar.py
python scripts/enriquecer_clippings.py
python scripts/atualizar_radares.py
python scripts/gerar_newsletter.py
python scripts/enviar_alertas.py --dry-run
```

---

## 3.2 Interface e movimento (23/11) — identidade "Newsroom institucional"

O Valor deixou de ser uma cópia do Assessor. Estrutura e visual próprios:

- **Masthead** com edição do dia, nav horizontal (`#/painel`, `#/midia`, `#/parlamentares`,
  `#/inteligencia`, `#/relatorios`, `#/sistema`) e filtros em faixa.
- **Papel + serifa**: Newsreader nos títulos/números, IBM Plex Mono nos rótulos, azul-marinho
  (`#1d3557`) e bronze (`#a8792f`). KPIs em faixa com filetes (sem cartões coloridos).
- **Telas**: Painel (edição + KPIs + notícias), Mídia (séries, share, valoração, top fontes),
  Parlamentares (Share of Voice + temas), Inteligência (radar/alertas + lexical + nuvem),
  Relatórios ("pranchas": PDF e newsletter) e Sistema (acesso + histórico).
- **Login em página inteira** com capa 3D isométrica própria (`assets/motion/hero-valor.mp4`).
- **Dois temas**: `Newsroom` claro (padrão) e `Edição da noite` (carvão + bronze); alternador no
  masthead e em Sistema, persistido em `localStorage.vp_tema`.
- **Gráficos**: rótulos nos pontos/barras, % nas fatias e total no centro, com as cores da identidade
  (tokens do tema). No mobile nada estoura a largura (tabelas rolam dentro do cartão).
- **Diagnóstico**: `?debug=1` liga o log do Firestore; erros vão para o console com contexto
  (`window.__erros`) e as leituras negadas logam coleção/escopo.
- **Regras**: admin/owner leem qualquer escopo (corrige o `permission-denied` ao filtrar por agente).
- **Esqueci minha senha** na tela de login (link do Firebase; template em `docs/emails/README.md`).
- **Ativos próprios**: `icons/favicon.svg` (pórtico), PNGs 192/512, maskable, apple-touch.
- **Motion**: assets em `frontend/assets/motion/`; splash do PWA próprio
  (`splash-vertical.mp4`, gerado de `SplashValorNovo` no estúdio do app principal).

### 3.2.1 Acesso e regras (23/11)

- As regras do `valorpublico-b1e6d` **não estavam publicadas** (o `config_acesso` dava
  `permission-denied`). Publicadas via Firebase Rules API com a service account (o deploy do
  CLI falhava com 403 nesta conta).
- `config_acesso/publico` = **restrito**; usuário `gestor.renatorosa@gmail.com` (papel admin,
  `chaves: ["geral"]`) com senha redefinida e provedor E-mail/Senha habilitado.
- O app agora **não inicializa** antes do login quando o modo é restrito.

## 4. Pendências## 4. Pendências

1. **Decidir o futuro**: operar de forma independente ou descontinuar (§3).
2. Se operar: configurar `.env`/secrets, rodar a rotina acima e o deploy
   (`firebase deploy --only hosting --project valorpublico-b1e6d`).
3. Aplicar as mesmas pendências do app principal: `IA_*` (não tem release aqui),
   `ALERTA_WEBHOOK_URL`/`SMTP_*` para entrega, `seed_acesso.py` para RBAC.
4. `frontend/index.html` foi reconstruído — vale revisar visualmente no navegador
   (título/branding e seções) antes de publicar.

---

## 5. Arquitetura e arquivos

Mesma estrutura do app principal. O que vale abrir primeiro:

| Caminho | Papel |
|---|---|
| `backend/processing/{mencao,trecho,compliance_eleitoral,propaganda_publica,alertas,cobertura,enriquecimento,valoracao}.py` | Camada DSM |
| `backend/config/fontes_radar.py` | fontes oficiais (Cuiabá, VG, ALMT/Estado) |
| `backend/scripts/` | `ingerir_radar`, `enriquecer_clippings`, `atualizar_radares`, `gerar_newsletter`, `enviar_alertas`, `exportar_camada_dsm`, `seed_acesso` |
| `frontend/js/dsm.js` · `frontend/js/auth.js` | painel da Camada DSM · login/escopo |
| `frontend/index.html` | reconstruído em `9272640` |
| `firestore.rules` | modo público × restrito por agente |

---

## 6. Armadilhas específicas

1. **`importmap`**: ao adicionar módulos do Firebase, registre-os no `importmap` do
   `index.html` (já tem `firebase/app`, `firebase/firestore` e `firebase/auth`).
2. **`frontend/index.html`** foi truncado no passado; se voltar a acontecer, reconstrua a partir
   do `HEAD` + as seções exigidas pelo `app.js`.
3. **Rules**: uma expressão por função; sem `String.replace()`.
4. **Nunca escrever clippings um a um** (cota) — use `db.batch()` (o backfill já faz 400/lote).
5. `window.__app_test` existe para o smoke test.

---

## 7. Documentos

- `README.md` — funcionalidades, arquitetura, execução.
- `CAMADA_DSM.md` — spec da camada de inteligência (idêntica à do app principal).
- `context.md` — **atenção**: a parte inicial descreve a stack "proposta" antiga
  (Node+Express/MongoDB), que nunca foi usada; o bloco final "Camada DSM (nov/2026)"
  é o estado real.
- `implementation.md` — roadmap por sprints (histórico).
- `D:\Dev\CerraClipping\STATUS_PROJETO.md` — master (inclui o Assessor Público).

---

## 8. Diário da sessão — 23/11/2026

- `core/quota.py` reposto; `main_com_cota` importado em `atualizar_metricas`/`exportar_clippings`;
  sanitização de `NaT/NaN` na gravação (mesma correção do app principal).
- **Regras publicadas pela primeira vez** via Rules API (o CLI desta conta dava 403); o
  `config_acesso` passou a responder sem `permission-denied`.
- Modo **restrito** ativo, com admin `gestor.renatorosa@gmail.com` (papel admin, `chaves:["geral"]`);
  provedor E-mail/Senha habilitado; `criar_usuario.py` disponível.
- Regras: admin/owner leem qualquer escopo — filtro por agente deixou de dar erro.
- **Identidade "Newsroom"** (claro + "Edição da noite"): masthead com edição, 6 telas por rota,
  Newsreader + Plex Mono, marca de pórtico, favicons/ícones próprios.
- Login em página inteira com capa 3D isométrica (hero reduzido), "Esqueci minha senha".
- Gráficos com valores/%/total e cores da identidade; sem overflow em 390/1440 nos dois temas.
- Diagnóstico: `window.__erros`, log contextual e `?debug=1`.
- Templates de e-mail prontos em `docs/emails/` (prévia + copiar); a API Admin recusa alterar o
  template (colagem no Console é manual).

### 1.4 Sessão 24/11/2026 — upgrade E0–E7

| Etapa | Entrega |
|---|---|
| E0 | `cerra_nucleo` v0.1.0 vendorizado (`backend/cerra_nucleo/`, `VERSION`, guarda de deriva em `tests/teste_nucleo.py`); SearXNG no lugar do CSE; coletor de Facebook público (sem cookies); páginas legais |
| E1 | tendências (Trends/Wikipédia/GDELT/YouTube), Telegram `t.me/s`, Ad Library, `demandas.py`, bairros, crise K-28, projeção K-33 |
| E1b | `midia` no `RawItem`; WebP+pHash; OCR RapidOCR; CLIP/VLM/rosto/C2PA prontos |
| E1c | `navegador.py`, `evidencia.py`, `previa_publica.py`, `receitas.py`; stealth público |
| E2 | `explicacoes.js`, `componentes.js`, `filtros.js`, `graficos.js`, `lexical.js`; telas novas; "Fatia da conversa" |
| E3 | CHD de Reinert real (rainette), corpus IRaMuTeQ, texto verificado, discurso (3 variantes), PDF |
| E4 | `conectar_conta.py`, `coletar_redes_proprias.py` (piloto) |
| E5 | `processar_demandas.py` (130 demandas reais) |
| E6 | `simulacao/` (MiroFish copiado + painel Nível 2 com IC 90%) |
| E7 | `docs/comercial/` |

**Novos comandos úteis:**
```powershell
cd backend
python tests/teste_nucleo.py            # 33 casos (tag do nucleo + salvaguardas)
python tests/teste_tendencias.py        # 29 casos (RSS, crise, projeção)
python tests/teste_imagem.py            # 28 casos (anti-SSRF, pHash, OCR)
python tests/teste_reinert.py           # 33 casos (rainette real)
python tests/teste_demandas.py          # 20 casos
python scripts/atualizar_tendencias.py  # grava metricas*.tendencias/.crise/.previsao
python scripts/processar_demandas.py --dias 400
python scripts/semanal/relatorio.py --escopo agente-<id>
python scripts/semanal/pdf.py
```
**Núcleo compartilhado:** editar em `D:\Dev\CerraClipping\cerra_nucleo` e rodar
`python tools/sync_nucleo.py` (copia para os dois apps e confere a deriva).

---

## 2. Sessão 24/11/2026 — separação total das 4 frentes

O Valor deixou de ser "um painel com todas as casas": depois do login o usuário
escolhe **uma** frente e o app só mostra os dados dela.

| Frente | `orgao` | Casa (`metricas_por_casa`) | Cidade (`metricas_por_cidade`) |
|---|---|---|---|
| Câmara de Cuiabá | `cuiaba` | `camara-cuiaba` | `cuiaba` |
| Câmara de Várzea Grande | `varzea-grande` | `camara-vg` | `varzea-grande` |
| Assembleia (ALMT) | `almt` | `almt` | `mato-grosso` |
| Governo de MT | `governo-mt` | `governo-mt` | `governo-de-mato-grosso` |

**Arquivos-chave:** `backend/core/orgaos.py` (mapa), `frontend/js/orgaos.js`
(espelho), `backend/scripts/carimbar_orgao.py` (migração do acervo),
`frontend/js/app.js` (seletor + escopo), `frontend/js/telas.js`/`dsm.js`
(leituras presas ao órgão), `frontend/js/governo.js` (só na frente Governo),
`firestore.rules` (leitura por `orgao`).

**Criar usuário de uma frente:** `python scripts/criar_usuario.py --email … --papel secom --orgao almt`
(ou `cuiaba`, `varzea-grande`, `governo-mt`). Admin (sem `--orgao`) vê as 4.

**Deploy feito:** regras publicadas via Rules API e Hosting `valorpublico` publicado.
Smoke de produção (Playwright) das 4 frentes: OK, 0 erro de permissão/JS; usuários
de teste removidos. Plano completo: `..\plano\20_SEPARACAO_FRENTES_VALOR_PUBLICO.md`.

---

## 3. Sessão 26/11/2026 — Instagram do Governo e botão Atualizar

### 3.1 Instagram do Governo (dados e imagens)

- Recapturados **44 posts** oficiais já existentes (curtidas e comentários). Exemplos: `DgIPl9rj4Xd` 592→**901** curtidas / 42→**61** comentários; `DgILra8kU2i` 690→**1.347** / 91→**128**; `DgF-W1aCuOt` 0→**1.861** / 0→**107**.
- Adicionados **9 posts novos** do `@govmatogrosso` com dados e imagens: `DgNeDnwuEk_`, `DgNM5usOIMI`, `DgLo4hBjome`, `DgLksAPAO1v`, `DgLVeC0BCl7`, `DgK7a0tCYyx`, `DgKztVEBgv-`, `DgKp-4okxNb` e `DgI8jKgFdV0`.
- Adicionados também **3 posts novos** do `@otavianopivetta`: `DgNXZBcoJls` (**1.602** curtidas / 165 comentários), `DgLVHO-yLiM` (**3.489** / 420) e `DgK3pkRx9yZ` (**4.344** / 490).
- `docs/instagram`: **56 posts únicos**, **1.344 comentários estruturados** e **1.400 registros**; capas, prints e carrosséis em `docs/instagram/<shortcode>/`.
- Firestore: `governo-mt` recebeu **546** documentos (33 posts + 513 comentários; 176 só de emoji descartados) e `governador-otaviano-pivetta` **499** (23 posts + 476 comentários; 179 descartados).
- Sentimento dos **1.345** comentários do Instagram reclassificado (léxico + VADER): **65** ajustes na última rodada.
- Agregados `metricas_por_casa/governo-mt` e `metricas_por_cidade/governo-de-mato-grosso`: **57 posts**, **1.345 comentários**; `imagens_governo/instagram` com **56 miniaturas** (856 KB).
- Sequência: `catalogar_instagram.py` → `carregar_instagram_valorpublico.py --agente …` → `atualizar_metricas_governo.py` → `publicar_miniaturas_instagram.py`.
- Integridade: **12 OK / 0 falhas**.

### 3.2 Regressão conhecida — botão Atualizar derruba a sessão

- `#btnAtualizar` limpa cache/service worker e chama `location.reload()` (`frontend/js/app.js:2020-2037`).
- No reload, `loginExplicito` volta a `false` (`app.js:2097-2101`); o bootstrap chama `sair()` mesmo com o usuário restaurado e abre o login (`app.js:2216-2222`); o handler `auth:changed` repete o gate (`app.js:1964-1968`).
- Teste com usuário temporário (removido): antes do botão, `authUser` preenchido e botão “Sair”; depois, `authUser = null`, login visível e botão “Entrar”. Bloqueando o `app.js` no reload, o Firebase restaurou o mesmo usuário — a persistência está OK.
- **Correção pendente:** no reload, chamar `entrarApp()` quando autenticado e remover o gate `loginExplicito`.

### 3.3 Correção do modal de post (Redes)

- O modal `#modalPost` agora fecha ao clicar no backdrop (fora do conteúdo), mantendo `X` e `Esc`.
- Alteração em `frontend/js/telas.js` (listener no overlay); **publicada no Hosting em 26/11**.
- Teste local com dados simulados em 1440×900 e 390×844: abre, fecha fora, **não** fecha clicando dentro e fecha no `X` — todos OK.

### 3.4 Ouvidoria — proposta 1 (26/11/2026)

- `demandas` populada com **32 manifestações** do Governo (14 pedidos, 8 perguntas, 6 reclamações, 4 sugestões); somente comentários de cidadãos. Respostas da própria conta oficial (`@govmatogrosso`/`@otavianopivetta`) foram descartadas.
- Temas: obras 6, meio ambiente 6, saúde 4, cultura 3, transporte 3, segurança 3, habitação 3, educação 2, serviços 2.
- **Municípios:** **37 de 633** comentários citam um município (Cuiabá 9, Várzea Grande 7, Juscimeira 3, Barra do Garças 3…; 18 municípios). O mapa usa essa contagem de menções e deixa claro que **não é a origem do cidadão**.
- **Sem autor no documento:** o resumo remove `@`/links e a fila não expõe cidadão; o texto fica no doc privado por órgão/papel.
- `tipo_manifestacao` (pedido/pergunta/reclamação/sugestão) e `pasta_sugerida` são gravados; o encaminhamento real continua humano.
- K-26 mostra a **idade média em aberto (~6,5 dias)**, com aviso de que não é tempo de resposta; para resposta real é preciso status/protocolo.
- Botão `(?)` (T-17) ao lado do mapa explica a proposta 2: para origem real por município e tempo de resposta é preciso criar um canal estruturado (formulário, WhatsApp ou DM) com campo de município e protocolo.
- Backend: `backend/scripts/processar_demandas.py` (`--orgao governo-mt --dias 400`).
- Front: 32 linhas com tag de tipo, coluna “Pasta sugerida”, mapas de temas e municípios populados.
- **Publicado no Hosting em 26/11** (sw `valorpublico-v54`), agora a partir do **diretório de trabalho** — preserva as melhorias da outra IA (print-only oculto, aba Simulação removida e `?` do discurso). Smoke ao vivo: 32 linhas, K-26 `6.5 dias`, “37 de 633” no mapa, 0 overflow/erro JS.
- **Menu:** `menu.js` inclui **Ouvidoria** na sidebar do Governo (grupo próprio) e no “Mais”.

### 3.5 Sessão 26/11/2026 (tarde) — vazamento, fontes do discurso e simulador do próprio discurso

**Vazamento de interface (corrigido em todas as telas)**

- `css/impressao.css` era carregado com `media="print"`, então o `.print-only { display: none; }`
  **nunca** era aplicado na tela: `#printCabecalho` (“ValorPúblico — Relatório”) e
  `#printRodape` (“ValorPúblico · documento institucional · gerado automaticamente”)
  apareciam em todas as telas.
- Correção: `<link rel="stylesheet" href="css/impressao.css" />` (sem `media`). O `@media print`
  interno continua valendo só no papel e `#printCabecalho`/`#printRodape` (id) continuam
  prevalecendo sobre `.print-only` (classe) na impressão.

**Fontes do discurso (tela Semana → Discurso; e governador/interino)**

- Causa do “Fonte” repetido: o backend publica as fontes como **texto**
  (`"Fatos de Mato Grosso, 2026-11-24"`) e o front esperava objetos (`f.veiculo`).
- `frontend/js/telas.js`: `normalizarFontes()` (aceita string ou objeto, separa veículo/data,
  deduplica) e `blocoFontes()` (botão **“Fontes (N)”** com veículo, data, link “abrir” e
  manchete). O link é resolvido cruzando o veículo com `noticias_recentes`; fonte em formato de
  domínio (`www.cbncuiaba.com.br`) é procurada dentro da URL da matéria.

**Botão `?` do discurso (D-01) e explicação da simulação (D-02)**

- `?` ao lado do selo “Rascunho gerado por IA”: explica coleta → briefing → redação (3 ângulos
  × 3 formatos) → validação → simulação → revisão humana.
- `explicacoes.js` ganhou o campo `passos` (lista numerada) e o popover ganhou altura máxima
  com rolagem.

**Aba “Simulação” da tela Semana**

- Removida da barra (ficava ao lado de “Discurso”). O relatório completo de simulação continua
  pelo link “ver relatório completo” dentro do discurso.

**Simulador do próprio discurso (novo, tela `#/personas`)**

- Front: `frontend/js/simulador.js` + painel em `index.html` (campo de texto, contador,
  “Avaliar com as 12 personas”, “Copiar resumo”, “Limpar”); KPIs (aderência média, personas que
  aderiram, risco médio, melhorias), “leitura do texto”, **“O que melhorar antes de publicar”**
  (prioridade, como reescrever, quem apontou), “O que funcionou” e a reação de cada persona.
- API: `POST /v1/discurso/simular` (`cloud/personas-api/app.py`) — 12 personas em paralelo
  (6 workers) + 1 consolidação; cada persona responde em JSON (aderência 0–10, risco 0–1,
  primeira impressão, o que funcionou, o que incomodou, sugestão, frase de risco) com as
  notícias da semana via RAG/BM25.
- Limites: `LIMITE_SIMULACAO_HORA=8` por usuário, discurso de 80 a 12.000 caracteres.
  Sem cache do conteúdo; prompt e resposta **não** são logados.
- Cloud Run: revisão `personas-api-00002-mqt`, `--timeout` de 60 s → **300 s**.
- Medido com a chave real do DeepSeek: 12 personas ~6 s + consolidação ~6 s = **~14 s**.
- Layout: 1440 e 390 px, tema claro e escuro.

**Publicação e estado**

- Hosting `valorpublico-v55` (publicado a partir do diretório de trabalho, preservando o
  trabalho da outra IA); conferência **produção == árvore de trabalho, arquivo por arquivo**.
- Commit `1604e54` (`origin/main`): front + API + triagem da ouvidoria.
- `.gitignore` passa a ignorar `docs/instagram/`, `docs/midiakit/`, `backend/data/imagens/` e
  `backend/*.err` (acervos locais pesados e/ou com dados de terceiros; repo é público).

**Pendências desta sessão**

1. **Teste ponta a ponta do simulador com usuário logado** — não foi possível forjar um Firebase
   ID token localmente; o caminho foi validado com a mesma chave do DeepSeek, mas falta rodar na
   sessão real e ver o resultado na tela.
2. Decidir se o resultado da simulação entra no **PDF de Personas** (hoje sai sem o painel).
3. Botão Atualizar continua derrubando a sessão (§3.2).
4. **API de personas respondendo 500 — DESLIGADA DE PROPÓSITO.** O dono desligou o plano **Blaze** em
   26/11/2026 e o Cloud Run deixou de servir (simulador e chat fora do ar). **Decisão do dono em
   26/11/2026: manter desligado até resolver a venda** — não migrar agora, não religar o Blaze.
   Quando o negócio for decidido, as opções continuam: religar o Blaze com alerta de orçamento,
   migrar para **Cloud Functions do Firebase (Spark)** (a RAG pesa 0,3 MB) ou Render Free.
   ⚠️ Consequência para a demonstração: o botão "Avaliar com as 12 personas" fica habilitado
   (a meta `personas-api` ainda aponta para a URL) e a falha aparece como erro genérico. Se for
   mostrar o painel a um cliente antes de resolver a venda, desligar o botão com mensagem honesta
   é a correção de 10 minutos (ou remover a meta do `frontend/index.html`).

### 3.6 Estratégia de compras públicas (26/11/2026) — pesquisa registrada

- `docs/comercial/ESTRATEGIA_COMPRAS_GOVERNO.md` (novo): vias de venda, o que sustenta (e o que não
  sustenta) a inexigibilidade, certificações e registros priorizados, a **obrigação do TCU sobre o
  atingimento de público-alvo**, regras de MT, 11 benchmarks de preço e plano de 90 dias.
- **O TCU cria o produto:** item **6.2(b) da Decisão Normativa TCU 134/2013** — "demonstração dos
  principais resultados das ações de publicidade e propaganda" — mais o **Acórdão 39/2003-Plenário,
  item 9.4(b)** ("atingimento dos objetivos previstos") e o **Acórdão 2.062/2006-Plenário, item 9.1.4**
  ("mecanismos efetivos de prestação de contas"). O decreto é da **Presidência** (6.555/2008, art. 10-D),
  não do TCU, e vale só para o Executivo federal. Nenhuma IN do TCU trata do tema.
- **Consequência no produto e nos documentos de venda:** novos requisitos **RF-13/14/15** e nova seção
  **§14 "Prestação de contas do alcance"** no `TR.md`; novo pacote **"Prova de atingimento"** e §7
  "vias de compra" no `PACOTES.md`; §§8–9 do `PESQUISA_PRECOS.md` com 11 contratos reais e a memória de
  cálculo do art. 3º da IN 65.
- **Venda:** pregão (padrão) → adesão a ARP federal → dispensa por valor (≤ R$ 65.492,11). Inexigibilidade
  é frágil para SaaS; as alavancas reais são a **margem de preferência do art. 26, §2º (20%)**, o
  **contrato de eficiência (art. 39)** e a própria obrigação do TCU.
