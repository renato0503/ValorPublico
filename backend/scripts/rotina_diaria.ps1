# Agendamento local (MVP) - Ingestao + metricas + analise lexical no Windows.
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
    python .\run_ingestao.py --apenas-sem-dados
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Ingestao falhou (exit $LASTEXITCODE)."
        exit 1
    }
}

Write-Host "-> Regenerando metricas"
python .\atualizar_metricas.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Metricas falharam (exit $LASTEXITCODE)."
    exit 1
}

# Analise lexical por escopo (IRAMUTEQ) + publicacao no Firestore — melhor esforco
Write-Host "-> Analise lexical por escopo (IRAMUTEQ)"
python .\analise_lexical_escopos.py --n-classes 4 --niveis 8
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Analise lexical por escopo falhou (exit $LASTEXITCODE) - continuando."
}

Write-Host "[$((Get-Date).ToString('s'))] Rotina concluida com sucesso."