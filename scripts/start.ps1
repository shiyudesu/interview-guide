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

function New-RandomSecret {
    $Bytes = New-Object byte[] 24
    $Generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $Generator.GetBytes($Bytes)
    }
    finally {
        $Generator.Dispose()
    }
    return -join ($Bytes | ForEach-Object { $_.ToString("x2") })
}

function Set-GeneratedSecret {
    param([string]$Name)
    $Targets = @("$Name=", "$Name=GENERATE_ON_FIRST_START")
    $Lines = [System.IO.File]::ReadAllLines((Join-Path $RepositoryRoot ".env"))
    if (-not ($Lines | Where-Object { $_ -in $Targets })) {
        return
    }
    $Replacement = "$Name=$(New-RandomSecret)"
    $Updated = $Lines | ForEach-Object { if ($_ -in $Targets) { $Replacement } else { $_ } }
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines((Join-Path $RepositoryRoot ".env"), $Updated, $Utf8NoBom)
}

function Initialize-EnvironmentFile {
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example."
    }
    Set-GeneratedSecret "POSTGRES_PASSWORD"
    Set-GeneratedSecret "APP_STORAGE_SECRET_KEY"
}

function Test-SupportedDockerArchitecture {
    $Architecture = (& docker info --format '{{.Architecture}}' 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Architecture) {
        Stop-WithMessage "Could not determine the Docker daemon architecture."
    }
    if ($Architecture -notin @("amd64", "x86_64", "arm64", "aarch64")) {
        Stop-WithMessage "Docker architecture $Architecture is unsupported. Production images support linux/amd64 and linux/arm64."
    }
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

function Show-ComposeRegistryFailure {
    param([string]$LogFile)
    $Content = Get-Content $LogFile -Raw
    $RegistryPattern = @(
        'registry-1\.docker\.io|auth\.docker\.io'
        'production\.cloudflare\.docker\.com|docker\.io/'
        'failed to resolve source metadata|failed to fetch anonymous token'
    ) -join '|'
    $NetworkPattern = @(
        'lookup |no such host|server misbehaving|temporary failure in name resolution'
        'dial tcp|connectex|i/o timeout|TLS handshake timeout'
        'context deadline exceeded|network is unreachable|connection refused'
        'connection reset|failed to do request|unexpected EOF'
    ) -join '|'
    if ($Content -notmatch $RegistryPattern -or $Content -notmatch $NetworkPattern) {
        return
    }
    Write-Host ""
    Write-Host "Docker registry networking or DNS resolution failed." -ForegroundColor Yellow
    Write-Host "- Docker Desktop: configure a working proxy in Settings > Resources > Proxies,"
    Write-Host "  then restart Docker Desktop."
    Write-Host "- Linux Docker Engine: configure a daemon proxy or a trusted Docker Hub"
    Write-Host "  registry mirror, then restart Docker."
    Write-Host "- If you already have a trusted Docker Hub pull-through cache, set this in .env:"
    Write-Host "    INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=mirror.example.com"
    Write-Host "  Use only a host name and optional path, without https://, and do not use an untrusted public mirror."
    Write-Host "After fixing daemon networking, verify it with 'docker pull docker.io/library/redis:7.4.2-alpine'."
    Write-Host "When using the .env registry override, run 'docker compose config --images' to confirm the image URLs."
    Write-Host "See 'Docker Hub image pull failures' in docs/OPERATIONS.md for details."
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

Initialize-EnvironmentFile
Test-SupportedDockerArchitecture

& docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "The Compose configuration is invalid. Check .env."
}

$FrontendPort = Get-ConfiguredPort "FRONTEND_PORT" 5173
$FrontendUrl = if ($FrontendPort -eq 80) { "http://localhost" } else { "http://localhost:$FrontendPort" }

Test-ConfiguredPorts

Write-Host "Building and starting services. The first run may take several minutes..."
$StartupLog = [System.IO.Path]::GetTempFileName()
try {
    & docker compose up -d --build --wait 2>&1 | Tee-Object -FilePath $StartupLog
    $ComposeExitCode = $LASTEXITCODE
    if ($ComposeExitCode -ne 0) {
        Show-ComposeRegistryFailure $StartupLog
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
Write-Host "API docs: $FrontendUrl/docs"
Write-Host "OpenAPI:  $FrontendUrl/openapi.json"
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
