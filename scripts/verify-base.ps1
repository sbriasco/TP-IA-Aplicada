[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [ValidateSet("cpu", "gpu")]
    [string]$Mode = "cpu"
)

$ErrorActionPreference = "Stop"
$python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
$envFile = Join-Path $ProjectRoot ".env"
$samplesPath = Join-Path $ProjectRoot ".verification\samples.json"
$privatePath = Join-Path $ProjectRoot ".verification\base-evidence.json"
$summaryPath = Join-Path $ProjectRoot "specs\002-entorno-arquitectura-base\validation\cpu-summary.json"

& (Join-Path $ProjectRoot "scripts\check-environment.ps1") -ProjectRoot $ProjectRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$fixtureSamples = @()
1..3 | ForEach-Object {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    Push-Location (Join-Path $ProjectRoot "backend")
    try {
        & $python -m pytest "tests/integration/test_worker_lifecycle.py::test_process_next_job_completes_and_persists_fixture" -q | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Falló la ejecución sintética $_." }
    } finally { Pop-Location }
    $watch.Stop()
    $fixtureSamples += [math]::Round($watch.Elapsed.TotalMilliseconds, 2)
}

$configuration = @{}
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $configuration[$matches[1].Trim()] = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
$healthUrl = "http://{0}:{1}/health" -f $configuration.FLOWSIGHT_API_HOST, $configuration.FLOWSIGHT_API_PORT
$apiProcess = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "flowsight.api.main:create_app", "--factory",
    "--host", $configuration.FLOWSIGHT_API_HOST, "--port", $configuration.FLOWSIGHT_API_PORT
) -WorkingDirectory (Join-Path $ProjectRoot "backend") -WindowStyle Hidden -PassThru
try {
    $ready = $false
    1..20 | ForEach-Object {
        if (-not $ready) {
            try {
                Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1 | Out-Null
                $ready = $true
            } catch { Start-Sleep -Milliseconds 250 }
        }
    }
    if (-not $ready) { throw "La API no inició para medir /health." }
    $healthSamples = @()
    1..3 | ForEach-Object {
        $watch = [System.Diagnostics.Stopwatch]::StartNew()
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        $watch.Stop()
        if ($response.status -ne "ok") { throw "Falló la consulta de salud $_." }
        $healthSamples += [math]::Round($watch.Elapsed.TotalMilliseconds, 2)
    }
} finally {
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
}

New-Item -ItemType Directory -Force -Path (Split-Path $samplesPath) | Out-Null
@{ fixture_ms = $fixtureSamples; health_ms = $healthSamples } |
    ConvertTo-Json | Set-Content -Encoding utf8 $samplesPath
& $python -m flowsight.core.environment_evidence --samples $samplesPath --private $privatePath --summary $summaryPath --mode $Mode
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-Content $summaryPath
