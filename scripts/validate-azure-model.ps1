[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [ValidateSet("inventory", "simple", "tools", "all")]
    [string]$Step = "all"
)

$ErrorActionPreference = "Stop"
$python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
$backend = Join-Path $ProjectRoot "backend"
$envFile = Join-Path $ProjectRoot ".env"
$validationDir = Join-Path $ProjectRoot "specs\003-validacion-modelo-azure\validation"

if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encontró el venv del backend en $python. Creá el entorno antes de validar Azure."
}

if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
} else {
    Write-Warning "No hay .env en la raíz; la validación fallará si faltan variables Azure."
}

New-Item -ItemType Directory -Force -Path $validationDir | Out-Null

Write-Host "=== FlowSight: validación Azure AI Foundry ($Step) ==="
Write-Host "API/worker de producto no requieren variables Azure para arrancar."
Write-Host "Este script solo usa FLOWSIGHT_AZURE_AI_* del .env local."

Push-Location $backend
try {
    & $python -m flowsight.llm.validate $validationDir --step $Step
    if ($LASTEXITCODE -ne 0) {
        throw "La validación finalizó con errores (revisá drafts en validation/; sin secretos)."
    }
} finally {
    Pop-Location
}

Write-Host "`nListo. Revisá $validationDir (sin versionar drafts crudos)."
