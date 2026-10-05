[CmdletBinding()]
param(
    [ValidateSet("Overload", "Stability")][string]$Scenario = "Overload",
    [ValidateRange(1,86400)][int]$DurationSeconds = 600,
    [int[]]$ProcessIds = @(),
    [string]$StorageDirectory = ""
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "backend/.venv/Scripts/python.exe"
$report = Join-Path $projectRoot ".verification/live-$Scenario-$(Get-Date -Format yyyyMMdd-HHmmss).json"
$arguments = @("tests/live_validation.py", "--scenario", $Scenario, "--duration", "$DurationSeconds", "--output", $report)
foreach ($processId in $ProcessIds) { $arguments += @("--process-id", "$processId") }
if ($StorageDirectory) { $arguments += @("--storage-directory", (Resolve-Path -LiteralPath $StorageDirectory).Path) }
Push-Location (Join-Path $projectRoot "backend")
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "El ensayo falló (exit $LASTEXITCODE)." }
    Write-Output "Reporte: $report"
} finally { Pop-Location }
