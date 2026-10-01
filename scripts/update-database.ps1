[CmdletBinding()]
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = "Stop"
$envFile = Join-Path $ProjectRoot ".env"
$python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $envFile)) { throw "Falta .env. Copiá .env.example y completalo." }
if (-not (Test-Path -LiteralPath $python)) { throw "Falta backend\.venv. Prepará el entorno del backend." }
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
if ([string]::IsNullOrWhiteSpace($env:FLOWSIGHT_DATABASE_URL)) { throw "Falta FLOWSIGHT_DATABASE_URL en .env." }
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Falló la migración. No borres ni recrees la base: revisá el error y volvé a intentarlo." }
} finally { Pop-Location }
