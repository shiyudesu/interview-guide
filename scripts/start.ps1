param(
    [switch]$NoOpen,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepositoryRoot

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host "Startup failed: $Message" -ForegroundColor Red
    exit 1
}

function Show-Diagnostics {
    Write-Host ""
    Write-Host "Container status:"
    & docker compose ps -a
    Write-Host ""
    Write-Host "Recent service logs:"
    & docker compose logs --tail=80 migrate app worker scheduler frontend
}

function Refresh-ProcessPath {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$MachinePath;$UserPath"
    $DockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
    if ((Test-Path $DockerBin) -and ($env:Path -notlike "*$DockerBin*")) {
        $env:Path = "$DockerBin;$env:Path"
    }
}

function Test-DockerCommand {
    Refresh-ProcessPath
    return $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
}

function Test-DockerCompose {
    if (-not (Test-DockerCommand)) {
        return $false
    }
    & docker compose version *> $null
    return $LASTEXITCODE -eq 0
}

function Test-DockerDaemon {
    if (-not (Test-DockerCommand)) {
        return $false
    }
    & docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Confirm-InstallDocker {
    if ($Yes) {
        return
    }
    $Answer = Read-Host "Docker Desktop is missing or incomplete. Install it now? [Y/n]"
    if ($Answer -and $Answer -notmatch '^(y|yes)$') {
        Stop-WithMessage "Docker Desktop installation was cancelled."
    }
}

function Install-DockerDesktop {
    Confirm-InstallDocker
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Stop-WithMessage "winget was not found. Install App Installer from Microsoft Store, or install Docker Desktop from https://docs.docker.com/desktop/setup/install/windows-install/"
    }
    Write-Host "Installing or upgrading Docker Desktop. Windows may request administrator approval..."
    & winget install --exact --id Docker.DockerDesktop --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "winget could not install Docker Desktop. Use https://docs.docker.com/desktop/setup/install/windows-install/"
    }
    Refresh-ProcessPath
    if (-not (Test-DockerCommand)) {
        Stop-WithMessage "Docker Desktop was installed, but the Docker CLI is not available yet. Restart the terminal and run this script again."
    }
}

function Start-DockerDesktop {
    $DesktopExecutable = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $DesktopExecutable) {
        Start-Process $DesktopExecutable
    }
}

function Wait-ForDocker {
    for ($Attempt = 1; $Attempt -le 90; $Attempt++) {
        if (Test-DockerDaemon) {
            return
        }
        if ($Attempt % 10 -eq 0) {
            Write-Host "Waiting for Docker Desktop ($Attempt/90)..."
        }
        Start-Sleep -Seconds 2
    }
    Stop-WithMessage "Docker Desktop did not become ready within 180 seconds. Complete any first-run prompts in Docker Desktop, then retry."
}

function Get-ConfiguredPort {
    param(
        [string]$Name,
        [int]$DefaultValue
    )
    $Line = Get-Content ".env" | Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } | Select-Object -Last 1
    if (-not $Line) {
        return $DefaultValue
    }
    $Value = ($Line -split "=", 2)[1]
    $Value = ($Value -split "#", 2)[0].Trim().Trim([char]34).Trim([char]39)
    $Parsed = 0
    if ([int]::TryParse($Value, [ref]$Parsed) -and $Parsed -ge 1 -and $Parsed -le 65535) {
        return $Parsed
    }
    return $DefaultValue
}

function Get-SuggestedPort {
    param(
        [string]$Name,
        [int]$Current
    )
    $Suggestion = switch ($Name) {
        "FRONTEND_PORT" { 5174 }
        "SERVER_PORT" { 18080 }
        "POSTGRES_PORT" { 15432 }
        "REDIS_PORT" { 16379 }
        "APP_STORAGE_PORT" { 19000 }
        "APP_STORAGE_CONSOLE_PORT" { 19001 }
        default { $Current + 10000 }
    }
    if ($Suggestion -eq $Current) {
        $Suggestion = $Current + 1000
    }
    if ($Suggestion -gt 65535) {
        $Suggestion = if ($Current -gt 1000) { $Current - 1000 } else { $Current + 1 }
    }
    for ($Attempt = 0; $Attempt -lt 20 -and (Test-PortInUse $Suggestion); $Attempt++) {
        $Suggestion++
        if ($Suggestion -gt 65535) {
            $Suggestion = 1024
        }
    }
    return $Suggestion
}

function Get-PortDefinitions {
    return @(
        [pscustomobject]@{ Name = "FRONTEND_PORT"; Port = Get-ConfiguredPort "FRONTEND_PORT" 5173; Label = "Frontend" }
        [pscustomobject]@{ Name = "SERVER_PORT"; Port = Get-ConfiguredPort "SERVER_PORT" 8080; Label = "API" }
        [pscustomobject]@{ Name = "POSTGRES_PORT"; Port = Get-ConfiguredPort "POSTGRES_PORT" 5432; Label = "PostgreSQL" }
        [pscustomobject]@{ Name = "REDIS_PORT"; Port = Get-ConfiguredPort "REDIS_PORT" 6379; Label = "Redis" }
        [pscustomobject]@{ Name = "APP_STORAGE_PORT"; Port = Get-ConfiguredPort "APP_STORAGE_PORT" 9000; Label = "MinIO API" }
        [pscustomobject]@{ Name = "APP_STORAGE_CONSOLE_PORT"; Port = Get-ConfiguredPort "APP_STORAGE_CONSOLE_PORT" 9001; Label = "MinIO Console" }
    )
}

function Test-PortInUse {
    param([int]$Port)
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Show-PortGuidance {
    param([object[]]$Definitions)
    Write-Host ""
    Write-Host "Host port conflicts were detected. Edit .env and change these mappings:" -ForegroundColor Yellow
    foreach ($Definition in $Definitions) {
        $Suggestion = Get-SuggestedPort $Definition.Name $Definition.Port
        Write-Host "- $($Definition.Label): port $($Definition.Port) is busy; try $($Definition.Name)=$Suggestion"
        $Connections = Get-NetTCPConnection -State Listen -LocalPort $Definition.Port -ErrorAction SilentlyContinue | Select-Object -First 3
        foreach ($Connection in $Connections) {
            $ProcessName = "unknown"
            try {
                $ProcessName = (Get-Process -Id $Connection.OwningProcess -ErrorAction Stop).ProcessName
            }
            catch {
            }
            Write-Host "    process=$ProcessName pid=$($Connection.OwningProcess) address=$($Connection.LocalAddress):$($Connection.LocalPort)"
        }
    }
    Write-Host ""
    Write-Host "Save .env and run the startup script again. Container-internal ports do not need to change."
    Write-Host "For example, FRONTEND_PORT=5174 changes the URL to http://localhost:5174."
}

function Test-ConfiguredPorts {
    $ProjectContainers = @(& docker compose ps -q 2>$null)
    if ($ProjectContainers.Count -gt 0) {
        return
    }
    $Conflicts = @(Get-PortDefinitions | Where-Object { Test-PortInUse $_.Port })
    if ($Conflicts.Count -gt 0) {
        Show-PortGuidance $Conflicts
        Stop-WithMessage "Resolve the port conflicts before starting the project."
    }
}

function Show-ComposePortFailure {
    param([string]$LogFile)
    $Content = Get-Content $LogFile -Raw
    if ($Content -notmatch '(?i)port is already allocated|address already in use|failed to bind host port|bind for .* failed') {
        return
    }
    $PortMatches = @(
        Get-PortDefinitions | Where-Object {
            $Content -match "[:.]$($_.Port)(?:[^0-9]|$)"
        }
    )
    if ($PortMatches.Count -eq 0) {
        $PortMatches = @(Get-PortDefinitions)
    }
    Show-PortGuidance $PortMatches
}

Write-Host "Checking local prerequisites..."

if (-not (Test-DockerCommand)) {
    Install-DockerDesktop
    if (-not (Test-DockerCommand)) {
        Stop-WithMessage "The Docker CLI is still unavailable. Restart Windows if requested by the installer, then retry."
    }
}

if (-not (Test-DockerCompose)) {
    Install-DockerDesktop
    if (-not (Test-DockerCompose)) {
        Stop-WithMessage "Docker Compose v2 is still unavailable. Restart Windows if requested by the installer, then retry."
    }
}

if (-not (Test-DockerDaemon)) {
    Write-Host "Docker Desktop is not running. Starting it now..."
    Start-DockerDesktop
    Wait-ForDocker
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example."
}

& docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "The Compose configuration is invalid. Check .env."
}

$FrontendPort = Get-ConfiguredPort "FRONTEND_PORT" 5173
$ServerPort = Get-ConfiguredPort "SERVER_PORT" 8080
$FrontendUrl = if ($FrontendPort -eq 80) { "http://localhost" } else { "http://localhost:$FrontendPort" }

Test-ConfiguredPorts

Write-Host "Building and starting services. The first run may take several minutes..."
$StartupLog = [System.IO.Path]::GetTempFileName()
try {
    & docker compose up -d --build --wait 2>&1 | Tee-Object -FilePath $StartupLog
    $ComposeExitCode = $LASTEXITCODE
    if ($ComposeExitCode -ne 0) {
        Show-ComposePortFailure $StartupLog
        Show-Diagnostics
        Stop-WithMessage "Compose did not start successfully. Review the diagnostics above and retry."
    }
}
finally {
    Remove-Item $StartupLog -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Startup completed." -ForegroundColor Green
& docker compose ps
Write-Host ""
Write-Host "Frontend: $FrontendUrl"
Write-Host "Settings: $FrontendUrl/settings"
Write-Host "API:    http://localhost:$ServerPort"
Write-Host ""
Write-Host "First-time setup: edit dashscope on the Settings page and enter the Bailian API Key."
Write-Host "Stop services: stop.cmd or scripts\stop.ps1"

if (-not $NoOpen) {
    try {
        Start-Process $FrontendUrl
    }
    catch {
        Write-Host "Could not open the browser automatically. Visit $FrontendUrl manually." -ForegroundColor Yellow
    }
}
