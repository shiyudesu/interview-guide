$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepositoryRoot

function Refresh-ProcessPath {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$MachinePath;$UserPath"
    $DockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
    if ((Test-Path $DockerBin) -and ($env:Path -notlike "*$DockerBin*")) {
        $env:Path = "$DockerBin;$env:Path"
    }
}

Write-Host "Stopping InterviewGuide local services..."
Refresh-ProcessPath

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker was not found. There are no Docker services this script can stop."
    exit 0
}

& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose v2 was not found, so project services cannot be identified." -ForegroundColor Red
    exit 1
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "The Docker daemon is not running. Project services are already unavailable."
    exit 0
}

& docker compose down --remove-orphans
if ($LASTEXITCODE -ne 0) {
    Write-Host "Shutdown failed. Run 'docker compose ps -a' and 'docker compose logs' for details." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Local services stopped." -ForegroundColor Green
Write-Host "PostgreSQL, Redis, MinIO, and Provider key volumes were preserved."
Write-Host "Start again with scripts\start.ps1 or start.cmd."
