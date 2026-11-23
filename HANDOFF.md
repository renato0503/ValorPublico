# HANDOFF — Valor Público

> Continuidade do app. Documento master do projeto: **`D:\Dev\CerraClipping\STATUS_PROJETO.md`**.
> Atualizado em 23/11/2026.

---

## 1. Onde paramos

O ValorPublico recebeu a mesma base do app principal (Assessor Público) e está sincronizado
em código. Commits:

| Commit | Entrega |
|---|---|
| `9272640` | **Camada DSM** — menção, trecho, compliance eleitoral, radar de propaganda pública, alertas, cobertura/SLA, AVPE, newsletter, painel `dsm.js`, regras. Inclui o **`frontend/index.html` reconstruído** (estava truncado em 17 bytes na working tree). |
| `93fa3ba` | **Completude** — entrega de alertas (SMTP/webhook), RBAC por agente, share of voice, PDF/CSV completos, testes + CI |

**Validado:** compilação OK · 23/23 testes da Camada DSM · 33/33 testes de regras ·
smoke test do painel no Chrome sem erros de JS.

---

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
- O código está pronto, mas `radar_publico`, `radares`, `alertas`, `cobertura` e `newsletters`
  **não foram populados aqui** (só no projeto do Assessor Público).

Para operar o ValorPublico como app independente:

```powershell
cd D:\Dev\CerraClipping\ValorPublico\backend
# .env com a service account do valorpublico-b1e6d
$env:FIREBASE_SERVICE_ACCOUNT="D:\Dev\CerraClipping\ValorPublico\backend\serviceAccountKey.json"
$env:FIREBASE_DATABASE_URL="https://valorpublico-b1e6d.firebaseio.com"

python scripts/run_ingestao.py
python scripts/atualizar_metricas.py
python scripts/ingerir_radar.py
python scripts/enriquecer_clippings.py
python scripts/atualizar_radares.py
python scripts/gerar_newsletter.py
python scripts/enviar_alertas.py --dry-run
```

---

## 4. Pendências

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
