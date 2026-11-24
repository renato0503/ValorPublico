param(
  [string]$Project = "valorpublico-b1e6d",
  [string]$Region = "southamerica-east1",
  [string]$Service = "personas-api",
  [string]$ServiceAccount = "firebase-adminsdk-fbsvc@valorpublico-b1e6d.iam.gserviceaccount.com"
)

$ErrorActionPreference = "Stop"
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) { throw "Crie cloud/personas-api/.env com DEEPSEEK_API_KEY antes de deployar." }
$linha = Get-Content $envFile | Where-Object { $_ -like "DEEPSEEK_API_KEY=*" } | Select-Object -First 1
if (-not $linha) { throw "DEEPSEEK_API_KEY ausente no .env." }
$chave = $linha.Substring("DEEPSEEK_API_KEY=".Length).Trim()
if (-not $chave) { throw "DEEPSEEK_API_KEY vazia." }

gcloud config set project $Project | Out-Null
Write-Host "Habilitando APIs (requer billing/owner)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --project $Project

$tmp = Join-Path $env:TEMP "deepseek-secret.txt"
[System.IO.File]::WriteAllText($tmp, $chave, (New-Object System.Text.UTF8Encoding($false)))
try {
  gcloud secrets describe deepseek-api-key --project $Project 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    gcloud secrets versions add deepseek-api-key --data-file=$tmp --project $Project | Out-Null
  } else {
    gcloud secrets create deepseek-api-key --data-file=$tmp --replication-policy=automatic --project $Project | Out-Null
  }
} finally {
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

gcloud secrets add-iam-policy-binding deepseek-api-key --project $Project `
  --member="serviceAccount:$ServiceAccount" --role="roles/secretmanager.secretAccessor" | Out-Null
gcloud projects add-iam-policy-binding $Project `
  --member="serviceAccount:$ServiceAccount" --role="roles/datastore.viewer" | Out-Null

Write-Host "Publicando Cloud Run (pode levar alguns minutos)..."
gcloud run deploy $Service --source $PSScriptRoot --project $Project --region $Region `
  --allow-unauthenticated `
  --service-account $ServiceAccount `
  --set-secrets "DEEPSEEK_API_KEY=deepseek-api-key:latest" `
  --set-env-vars "FIREBASE_PROJECT_ID=$Project,ALLOWED_ORIGINS=https://valorpublico.web.app" `
  --memory 512Mi --timeout 60 --port 8080

$url = gcloud run services describe $Service --project $Project --region $Region --format="value(status.url)"
Write-Host ""
Write-Host "API publicada em: $url"
Write-Host "Agora coloque no frontend/index.html:"
Write-Host "  <meta name=`"personas-api`" content=`"$url`" />"
Write-Host "e faca o deploy do hosting."
