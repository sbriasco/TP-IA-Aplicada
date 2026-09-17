[CmdletBinding()]
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = "Stop"
$envFile = Join-Path $ProjectRoot ".env"
$python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $envFile)) { throw "Falta .env. Copiá .env.example y completalo." }
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $python -m uvicorn flowsight.api.main:create_app --factory --host $env:FLOWSIGHT_API_HOST --port $env:FLOWSIGHT_API_PORT
} finally { Pop-Location }
