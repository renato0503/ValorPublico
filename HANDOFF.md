# HANDOFF — Valor Público

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

Estado: **74 agentes** (`count()`=74), métricas recalculadas sobre **7.228 clippings** (3 escopos:
Cuiabá, Várzea Grande, Mato Grosso) e `metricas/geral.redes_sociais` presente (Instagram 6,
Facebook 4, Twitter 1, TikTok 1; 12 recentes). O cron do `redes_almt.yml` só deve ser ativado
após confirmação do dono. Não houve push/deploy.

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
