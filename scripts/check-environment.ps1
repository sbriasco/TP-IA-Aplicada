[CmdletBinding()]
param(
    [ValidateSet("Text", "Json")]
    [string]$OutputFormat = "Text",
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$EnvFile,
    [string]$PythonPath,
    [string]$PostgresBin
)

$ErrorActionPreference = "Stop"
$startedAt = [System.Diagnostics.Stopwatch]::StartNew()
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Component, [bool]$Passed, [string]$Message)
    $checks.Add([pscustomobject]@{
        component = $Component
        status = if ($Passed) { "ok" } else { "failed" }
        message = $Message
    })
}

if (-not $EnvFile) { $EnvFile = Join-Path $ProjectRoot ".env" }
if (-not $PythonPath) {
    $PythonPath = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
}

$configuration = @{}
if (Test-Path -LiteralPath $EnvFile) {
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $configuration[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$requiredVariables = @(
    "FLOWSIGHT_ENV",
    "FLOWSIGHT_DATABASE_URL",
    "FLOWSIGHT_API_HOST",
    "FLOWSIGHT_API_PORT",
    "FLOWSIGHT_WORKER_ID",
    "FLOWSIGHT_PREVIEW_MAX_FPS",
    "VITE_API_BASE_URL",
    "VITE_WS_BASE_URL"
)
$missingVariables = @($requiredVariables | Where-Object {
    -not $configuration.ContainsKey($_) -or [string]::IsNullOrWhiteSpace($configuration[$_])
})
if ($missingVariables.Count -eq 0) {
    Add-Check "Configuracion" $true "Variables obligatorias presentes en .env."
} else {
    Add-Check "Configuracion" $false (
        "Faltan variables: {0}. Copiá .env.example y completalas." -f ($missingVariables -join ", ")
    )
}

if (Test-Path -LiteralPath $PythonPath) {
    $pythonVersion = & $PythonPath -c "import platform; print(platform.python_version()); print(platform.architecture()[0])"
    $pythonOk = $LASTEXITCODE -eq 0 -and $pythonVersion[0] -eq "3.11.16" -and $pythonVersion[1] -eq "64bit"
    Add-Check "Python" $pythonOk ("Versión {0}, {1}. Requerida: 3.11.16 de 64 bits." -f $pythonVersion[0], $pythonVersion[1])
    & $PythonPath -c "import alembic, fastapi, psycopg, pydantic_settings, sqlalchemy" 2>$null
    $backendDependenciesReady = $LASTEXITCODE -eq 0
    $backendDependenciesMessage = if ($backendDependenciesReady) {
        "Dependencias principales disponibles."
    } else {
        "Faltan paquetes. Instalá backend/requirements.lock."
    }
    Add-Check "Dependencias backend" $backendDependenciesReady $backendDependenciesMessage
} else {
    Add-Check "Python" $false "No se encontró backend/.venv. Creá el entorno con Python 3.11.16."
    Add-Check "Dependencias backend" $false "No se verificaron porque falta backend/.venv."
}

$expectedNode = (Get-Content -Raw (Join-Path $ProjectRoot ".node-version")).Trim()
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) {
    $nodeVersion = (& node --version).TrimStart("v")
    Add-Check "Node.js" ($nodeVersion -eq $expectedNode) "Versión $nodeVersion. Requerida: $expectedNode."
} else {
    Add-Check "Node.js" $false "Node.js no está disponible. Instalá la versión de .node-version."
}

$npmCommand = Get-Command npm -ErrorAction SilentlyContinue
if ($npmCommand) {
    Add-Check "npm" $true ("Versión {0}." -f (& npm --version))
} else {
    Add-Check "npm" $false "npm no está disponible junto con Node.js."
}

$vitePackage = Join-Path $ProjectRoot "frontend\node_modules\vite\package.json"
$frontendDependenciesReady = Test-Path -LiteralPath $vitePackage
$frontendDependenciesMessage = if ($frontendDependenciesReady) {
    "Dependencias del lockfile disponibles."
} else {
    "Falta frontend/node_modules. Ejecutá npm ci en frontend."
}
Add-Check "Dependencias frontend" $frontendDependenciesReady $frontendDependenciesMessage

$psqlPath = $null
if ($PostgresBin) {
    $candidate = Join-Path $PostgresBin "psql.exe"
    if (Test-Path -LiteralPath $candidate) { $psqlPath = $candidate }
} else {
    $localCandidate = Join-Path $ProjectRoot ".tools\postgresql-17\pgsql\bin\psql.exe"
    if (Test-Path -LiteralPath $localCandidate) {
        $psqlPath = $localCandidate
    } else {
        $psqlCommand = Get-Command psql -ErrorAction SilentlyContinue
        if ($psqlCommand) { $psqlPath = $psqlCommand.Source }
    }
}

if ($psqlPath) {
    $postgresVersion = (& $psqlPath --version)
    Add-Check "PostgreSQL" ($postgresVersion -match " 17\.") $postgresVersion
} else {
    Add-Check "PostgreSQL" $false "No se encontró psql. Instalá PostgreSQL 17 o indicá -PostgresBin."
}

$databaseReady = $false
if ($psqlPath -and $missingVariables.Count -eq 0) {
    try {
        $safeUrl = $configuration["FLOWSIGHT_DATABASE_URL"] -replace "^postgresql\+psycopg", "postgresql"
        $databaseUri = [uri]$safeUrl
        $credentials = $databaseUri.UserInfo.Split(":", 2)
        $databaseName = $databaseUri.AbsolutePath.TrimStart("/")
        $previousPassword = $env:PGPASSWORD
        $env:PGPASSWORD = [uri]::UnescapeDataString($credentials[1])
        try {
            & $psqlPath -w -h $databaseUri.Host -p $databaseUri.Port -U $credentials[0] -d $databaseName -c "SELECT 1" 2>$null | Out-Null
            $databaseReady = $LASTEXITCODE -eq 0
        } finally {
            $env:PGPASSWORD = $previousPassword
        }
    } catch {
        $databaseReady = $false
    }
    $databaseMessage = if ($databaseReady) {
        "Conexión local disponible."
    } else {
        "No responde. Iniciá PostgreSQL y revisá .env."
    }
    Add-Check "Base de datos" $databaseReady $databaseMessage
} else {
    Add-Check "Base de datos" $false "No se verificó porque falta PostgreSQL o configuración."
}

$startedAt.Stop()
$ready = @($checks | Where-Object { $_.status -eq "failed" }).Count -eq 0
$report = [pscustomobject]@{
    status = if ($ready) { "ready" } else { "failed" }
    duration_ms = [math]::Round($startedAt.Elapsed.TotalMilliseconds, 2)
    checks = $checks
}

if ($OutputFormat -eq "Json") {
    $report | ConvertTo-Json -Depth 5
} else {
    $report.checks | Format-Table -AutoSize
    Write-Output ("Estado: {0}. Duración: {1} ms." -f $report.status, $report.duration_ms)
}

if (-not $ready) { exit 1 }
