# Agendamento local (MVP) - Ingestao + metricas no Windows.
# Uso: rodar via "Agendador de Tarefas" do Windows (opcional).
# Alternativa em nuvem: .github/workflows/ingestao.yml (GitHub Actions).

param(
    [switch]$SomenteMetricas
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "[$((Get-Date).ToString('s'))] Iniciando rotina diaria do ValorPublico..."

if (-not $SomenteMetricas) {
    Write-Host "-> Ingestao Web"
    python .\scripts\run_ingestao.py --apenas-sem-dados
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Ingestao falhou (exit $LASTEXITCODE)."
        exit 1
    }
}

Write-Host "-> Regenerando metricas"
python .\scripts\atualizar_metricas.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Metricas falharam (exit $LASTEXITCODE)."
    exit 1
}

Write-Host "[$((Get-Date).ToString('s'))] Rotina concluida com sucesso."