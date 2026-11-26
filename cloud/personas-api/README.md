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

## 6. Endpoints

Todos exigem **Firebase ID token** (`Authorization: Bearer <token>`) e usuário com
`orgao` = `governo-mt` ou `admin`.

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/health` | Estado da API (sem auth): nº de personas, versão da RAG, modelo e se a chave existe. |
| `GET` | `/v1/personas` | Lista as personas e a versão da RAG. |
| `POST` | `/v1/personas/{id}/perguntar` | Chat com **uma** persona: `{ pergunta }` → resposta em 1ª pessoa com citações `[1]`, `[2]`. |
| `POST` | `/v1/discurso/simular` | **Simulador de discurso** (26/11/2026): `{ discurso }` → as 12 personas reagem de uma vez. |

### `POST /v1/discurso/simular`

```jsonc
// entrada
{ "discurso": "texto do usuário (80 a 12.000 caracteres)",
  "personas": ["opcional: ids das personas"] }
```

```jsonc
// saída (resumo do contrato)
{
  "discurso": { "palavras": 412, "caracteres": 2680 },
  "resumo": { "aderencia_media": 5.6, "aderencia_min": 2.0, "aderencia_max": 9.0,
              "risco_medio": 0.42, "personas_alta": 4, "personas_baixa": 3,
              "total_personas": 12 },
  "veredito": "leitura geral do texto",
  "pontos_fortes": ["..."],
  "melhorias": [ { "titulo": "...", "como_reescrever": "...",
                   "personas": ["rótulo"], "prioridade": "alta|media|baixa" } ],
  "personas": [ { "id": "...", "rotulo": "...", "aderencia": 0-10, "risco": 0-1,
                  "primeira_impressao": "...", "o_que_funciona": "...",
                  "o_que_incomoda": "...", "sugestao": "...", "frase_de_risco": "...",
                  "citacoes": [ { "titulo": "...", "url": "...", "data": "..." } ] } ],
  "aviso": "Simulação (hipótese) — as personas são sintéticas...",
  "modelo": "deepseek-chat", "versao_rag": "2026-W48-v1", "latencia_ms": 14000
}
```

Regras:

- **Custo:** 12 chamadas ao DeepSeek em paralelo (6 workers) + 1 chamada de consolidação.
  Medido em produção: **~6 s** para as personas + **~6 s** para consolidar (~14 s no total).
- **Limite:** `LIMITE_SIMULACAO_HORA` (padrão **8** simulações por hora por usuário) e
  `DISCURSO_MIN_CHARS` (80) / `DISCURSO_MAX_CHARS` (12.000). Excedeu: **429**.
- **Timeout do Cloud Run:** 300 s (`deploy.ps1`). A tela do front mostra "Avaliando com as
  12 personas…" enquanto espera.
- **Sem cache:** o mesmo texto pode ser reavaliado (a cota é do usuário, não do conteúdo).
- **Segurança:** o prompt e a resposta **não são logados**; o log traz apenas persona,
  uid, nº de trechos e latência.
- **Fallback:** se a consolidação falhar ou vier truncada, a API devolve as sugestões das
  personas mais críticas e um "veredito" extraído por regex do texto bruto.

Variáveis de ambiente relacionadas:

| Variável | Padrão | O que controla |
|---|---|---|
| `LIMITE_SIMULACAO_HORA` | `8` | simulações por hora por usuário |
| `DISCURSO_MIN_CHARS` | `80` | tamanho mínimo do discurso |
| `DISCURSO_MAX_CHARS` | `12000` | tamanho máximo enviado à IA |
| `PARALELISMO` | `6` | personas avaliadas ao mesmo tempo |
