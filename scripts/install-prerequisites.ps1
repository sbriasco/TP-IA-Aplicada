# Baja Python 3.11.16, Node.js 22.20.0 y PostgreSQL 17 a .tools/ (no va a Git)
# y deja backend\.venv más la base local del .env.example.
# No instala las librerías del lock ni el PyTorch de la RTX: eso sigue en el README.
[CmdletBinding()]
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.11.16%2B20260901-x86_64-pc-windows-msvc-install_only.tar.gz"
$NodeUrl = "https://nodejs.org/dist/v22.20.0/node-v22.20.0-win-x64.zip"
$PostgresUrl = "https://get.enterprisedb.com/postgresql/postgresql-17.6-1-windows-x64-binaries.zip"
$ExpectedPython = "3.11.16"
$ExpectedNode = (Get-Content -Raw (Join-Path $ProjectRoot ".node-version")).Trim()

$ToolsDir = Join-Path $ProjectRoot ".tools"
$DownloadDir = Join-Path $ToolsDir "_downloads"
$PythonHome = Join-Path $ToolsDir "python-3.11.16"
$NodeHome = Join-Path $ToolsDir "node"
$PostgresHome = Join-Path $ToolsDir "postgresql-17"
$PostgresBin = Join-Path $PostgresHome "pgsql\bin"
$DataDir = Join-Path $ProjectRoot ".postgres-data"
$VenvPython = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
$DatabaseName = "flowsight"
$DatabaseUser = "flowsight"
$DatabasePassword = "flowsight"
$DatabasePort = 5432

function Save-Url {
    param([string]$Url, [string]$Destination)
    Write-Output "Descargando $Url"
    & curl.exe -L --fail --silent --show-error --output $Destination $Url
    if ($LASTEXITCODE -ne 0) { throw "No se pudo descargar $Url" }
}

function Test-TcpPort {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-PythonVersion {
    param([string]$PythonExe)
    $version = & $PythonExe -c "import platform; print(platform.python_version()); print(platform.architecture()[0])"
    if ($LASTEXITCODE -ne 0) { return $null }
    return $version
}

New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null

$venvReady = $false
if (Test-Path -LiteralPath $VenvPython) {
    $installed = Get-PythonVersion $VenvPython
    $venvReady = $installed -and $installed[0] -eq $ExpectedPython -and $installed[1] -eq "64bit"
}

if ($venvReady) {
    Write-Output "Python $ExpectedPython ya está en backend\.venv."
} else {
    $basePython = Join-Path $PythonHome "python\python.exe"
    if (-not (Test-Path -LiteralPath $basePython)) {
        $archive = Join-Path $DownloadDir "cpython-3.11.16-windows.tar.gz"
        Save-Url $PythonUrl $archive
        if (Test-Path -LiteralPath $PythonHome) {
            Remove-Item -LiteralPath $PythonHome -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $PythonHome | Out-Null
        & tar.exe -xzf $archive -C $PythonHome
        if ($LASTEXITCODE -ne 0) { throw "No se pudo extraer Python." }
        Remove-Item -LiteralPath $archive -Force
    }
    $found = Get-ChildItem -LiteralPath $PythonHome -Filter python.exe -Recurse -File |
        Select-Object -First 1
    if (-not $found) { throw "La descarga de Python no trae python.exe." }
    $checked = Get-PythonVersion $found.FullName
    if (-not $checked -or $checked[0] -ne $ExpectedPython -or $checked[1] -ne "64bit") {
        throw "Se esperaba Python $ExpectedPython de 64 bits."
    }
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "backend\.venv")) {
        throw "backend\.venv existe pero no es Python $ExpectedPython. Borralo y volvé a correr este script."
    }
    & $found.FullName -m venv (Join-Path $ProjectRoot "backend\.venv")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear backend\.venv." }
    Write-Output "Python $ExpectedPython quedó en backend\.venv."
}

$nodeExe = Join-Path $NodeHome "node.exe"
$nodeReady = $false
if (Test-Path -LiteralPath $nodeExe) {
    $nodeVersion = (& $nodeExe --version).TrimStart("v")
    $nodeReady = $nodeVersion -eq $ExpectedNode
}
if (-not $nodeReady) {
    $pathNode = Get-Command node -ErrorAction SilentlyContinue
    if ($pathNode) {
        $pathVersion = (& $pathNode.Source --version).TrimStart("v")
        if ($pathVersion -eq $ExpectedNode) {
            $nodeExe = $pathNode.Source
            $nodeReady = $true
            Write-Output "Node.js $ExpectedNode ya está en el PATH."
        }
    }
}
if (-not $nodeReady) {
    $archive = Join-Path $DownloadDir "node-v22.20.0-win-x64.zip"
    $staging = Join-Path $DownloadDir "node-staging"
    Save-Url $NodeUrl $archive
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
    $found = Get-ChildItem -LiteralPath $staging -Filter node.exe -Recurse -File | Select-Object -First 1
    if (-not $found) { throw "La descarga de Node.js no trae node.exe." }
    if (Test-Path -LiteralPath $NodeHome) { Remove-Item -LiteralPath $NodeHome -Recurse -Force }
    Copy-Item -LiteralPath $found.Directory.FullName -Destination $NodeHome -Recurse
    Remove-Item -LiteralPath $archive -Force
    Remove-Item -LiteralPath $staging -Recurse -Force
    $nodeExe = Join-Path $NodeHome "node.exe"
    $nodeVersion = (& $nodeExe --version).TrimStart("v")
    if ($nodeVersion -ne $ExpectedNode) { throw "Se esperaba Node.js $ExpectedNode y llegó $nodeVersion." }
    Write-Output "Node.js $ExpectedNode quedó en .tools\node."
}

if ($nodeExe -eq (Join-Path $NodeHome "node.exe")) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @()
    if ($userPath) { $entries = @($userPath.Split(";") | Where-Object { $_ }) }
    if ($entries -notcontains $NodeHome) {
        $updated = (@($NodeHome) + $entries) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $updated, "User")
        Write-Output "Agregué .tools\node al PATH del usuario. Abrí una terminal nueva para usar npm."
    }
}

$psql = Join-Path $PostgresBin "psql.exe"
if (-not (Test-Path -LiteralPath $psql)) {
    $archive = Join-Path $DownloadDir "postgresql-17.6-windows-x64-binaries.zip"
    $staging = Join-Path $DownloadDir "postgres-staging"
    Save-Url $PostgresUrl $archive
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
    $found = Get-ChildItem -LiteralPath $staging -Filter psql.exe -Recurse -File | Select-Object -First 1
    if (-not $found) { throw "La descarga de PostgreSQL no trae psql.exe." }
    $pgsqlDir = $found.Directory.Parent.FullName
    $destination = Join-Path $PostgresHome "pgsql"
    if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $PostgresHome | Out-Null
    Move-Item -LiteralPath $pgsqlDir -Destination $destination
    Remove-Item -LiteralPath $archive -Force
    Remove-Item -LiteralPath $staging -Recurse -Force
}
$versionLine = & $psql --version
if ($versionLine -notmatch " 17\.") { throw "Se esperaba PostgreSQL 17 y psql informa: $versionLine" }
Write-Output "PostgreSQL quedó en .tools\postgresql-17 ($versionLine)."

$envExample = Join-Path $ProjectRoot ".env.example"
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path -LiteralPath $envFile) -and (Test-Path -LiteralPath $envExample)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Output "Copié .env.example a .env."
}

$pgCtl = Join-Path $PostgresBin "pg_ctl.exe"
$initdb = Join-Path $PostgresBin "initdb.exe"
$pgIsReady = Join-Path $PostgresBin "pg_isready.exe"
$clusterReady = Test-Path -LiteralPath (Join-Path $DataDir "PG_VERSION")
$setupPasswordFile = Join-Path $DataDir "setup-password.txt"

if (-not $clusterReady) {
    if (Test-TcpPort $DatabasePort) {
        throw "El puerto $DatabasePort ya está en uso. Los programas quedaron en .tools. Apuntá FLOWSIGHT_DATABASE_URL a ese PostgreSQL o liberá el puerto y volvé a correr el script."
    }
    $passwordFile = Join-Path $DownloadDir "pg-superuser.txt"
    $superPassword = [guid]::NewGuid().ToString("N")
    [System.IO.File]::WriteAllText($passwordFile, $superPassword)
    & $initdb -D $DataDir -U postgres -A scram-sha-256 -E UTF8 --pwfile=$passwordFile --no-locale
    $initOk = $LASTEXITCODE -eq 0
    Remove-Item -LiteralPath $passwordFile -Force -ErrorAction SilentlyContinue
    if (-not $initOk) {
        if (Test-Path -LiteralPath $DataDir) { Remove-Item -LiteralPath $DataDir -Recurse -Force }
        throw "initdb falló. Si falta el runtime de Visual C++, instalá el redistribuible de Microsoft y volvé a correr el script."
    }
    [System.IO.File]::WriteAllText($setupPasswordFile, $superPassword)
} elseif (Test-Path -LiteralPath $setupPasswordFile) {
    $superPassword = [System.IO.File]::ReadAllText($setupPasswordFile).Trim()
} else {
    $superPassword = $null
}

& $pgCtl -D $DataDir status 2>$null | Out-Null
$ownServerRunning = $LASTEXITCODE -eq 0
if (-not $ownServerRunning) {
    if (Test-TcpPort $DatabasePort) {
        throw "Hay otro PostgreSQL en el puerto $DatabasePort. No lo modifiqué. Apuntá FLOWSIGHT_DATABASE_URL a ese servidor o liberá el puerto y volvé a correr el script."
    }
    & $pgCtl -D $DataDir -l (Join-Path $DataDir "server.log") start
    if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar PostgreSQL. Mirá .postgres-data\server.log." }
    $ownServerRunning = $true
}

$ready = $false
if ($ownServerRunning) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        & $pgIsReady -h 127.0.0.1 -p $DatabasePort | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) { throw "PostgreSQL no respondió en 127.0.0.1:$DatabasePort." }

if ($superPassword) {
    $previousPassword = $env:PGPASSWORD
    $env:PGPASSWORD = $superPassword
    try {
        & $psql -w -h 127.0.0.1 -p $DatabasePort -U postgres -d postgres -v ON_ERROR_STOP=1 -c @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DatabaseUser') THEN
    CREATE ROLE $DatabaseUser LOGIN PASSWORD '$DatabasePassword';
  END IF;
END
`$`$;
"@
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el usuario $DatabaseUser." }
        $exists = & $psql -w -tA -h 127.0.0.1 -p $DatabasePort -U postgres -d postgres -c "SELECT 1 FROM pg_database WHERE datname = '$DatabaseName'"
        if ($LASTEXITCODE -ne 0) { throw "No se pudo consultar la base $DatabaseName." }
        if (-not (($exists | Out-String).Trim())) {
            & $psql -w -h 127.0.0.1 -p $DatabasePort -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DatabaseName OWNER $DatabaseUser"
            if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la base $DatabaseName." }
        }
    } finally {
        if ($null -eq $previousPassword) {
            Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        } else {
            $env:PGPASSWORD = $previousPassword
        }
    }
    Write-Output "Base local lista: usuario y base $DatabaseName en 127.0.0.1:$DatabasePort, como en .env.example."
} else {
    Write-Output "El directorio .postgres-data ya existía y no tengo su clave de administrador. No cambié usuarios ni contraseñas."
}

Write-Output "Listo. Siguiente: pip y npm, como indica el README. Este script no instala el PyTorch de la RTX."
