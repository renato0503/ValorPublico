# Personas API — deploy no Render Free

A API de personas usa FastAPI + BM25 + DeepSeek. O Cloud Run depende de Blaze;
o Render Free cobre o chat sem billing.

## 1. Pré-requisitos

- Conta no [Render](https://render.com).
- Repositório `renato0503/ValorPublico` conectado.
- Pacote RAG em `cloud/personas-api/data/personas_export` (versionado no repo).
- Chave DeepSeek e JSON da service account do Firebase.

## 2. Segredos (nunca no git)

No Render, configure:

| Variável | Valor |
|---|---|
| `DEEPSEEK_API_KEY` | chave DeepSeek (secret) |
| `FIREBASE_SERVICE_ACCOUNT_B64` | service account JSON em base64 (secret) |
| `FIREBASE_PROJECT_ID` | `valorpublico-b1e6d` |
| `ALLOWED_ORIGINS` | `https://valorpublico.web.app` |

Gerar o base64 localmente (sem imprimir a chave no chat):

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("D:\Dev\CerraClipping\ValorPublico\backend\serviceAccountKey.json"))
```

## 3. Deploy

Opção A — Blueprint: New → Blueprint → repositório → `render.yaml`.
Opção B — manual: New → Web Service → Docker → Root Directory `cloud/personas-api` → Plan Free.

O health check é `GET /health`.

## 4. Ligar no front

Copie a URL do Render e coloque em `frontend/index.html`:

```html
<meta name="personas-api" content="https://SEU-SERVICO.onrender.com" />
```

Depois faça o deploy do Hosting. O `personas.js` lê essa meta e habilita o chat.

## 5. Observações

- O plano free hiberna após inatividade; a primeira pergunta pode demorar ~30 s.
- A API valida Firebase ID token e `orgao` (governo-mt/admin).
- A chave DeepSeek e o JSON da service account são secrets do Render; não vão para o repo.

## Cloud Run (Blaze ativo)

Pré-requisitos (com sua conta **owner**, não a service account):

```powershell
gcloud auth login
gcloud config set project valorpublico-b1e6d
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

Depois:

```powershell
cd D:\Dev\CerraClipping\ValorPublico\cloud\personas-api
.\deploy.ps1
```

O script:
- lê a chave do `.env` local (nunca imprime);
- cria/atualiza o segredo `deepseek-api-key`;
- concede `secretAccessor` e `datastore.viewer` à service account do Cloud Run;
- publica o serviço `personas-api` em `southamerica-east1` com `--allow-unauthenticated` (a API valida o Firebase ID token);
- imprime a URL para colocar no `<meta name="personas-api">`.

Se a conta ativa for `firebase-adminsdk-*`, o script para e pede `gcloud auth login`
(essa SA não tem permissão de Cloud Run/Service Usage).
