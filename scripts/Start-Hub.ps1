# Starts the whole development environment with one command, then checks that it answers.
#   .\scripts\Start-Hub.ps1
# Infrastructure (MongoDB, Redis, Mailpit) runs in Docker and restarts on its own; the application
# processes (Django, Celery, course worker, Vite) open in minimised windows. Already running parts are kept.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$celery = Join-Path $root 'backend\.venv\Scripts\celery.exe'
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

function Test-Port([int] $port) {
    [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
function Wait-Port([int] $port, [string] $name, [int] $seconds = 60) {
    for ($i = 0; $i -lt $seconds; $i++) { if (Test-Port $port) { return }; Start-Sleep -Seconds 1 }
    throw "$name ne répond pas sur le port $port."
}
function Start-Container([string] $name, [string] $image, [string[]] $runArgs) {
    if (docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $name }) { docker start $name | Out-Null }
    else { docker run -d --name $name --restart unless-stopped @runArgs $image | Out-Null }
}
function Test-Process([string] $pattern) {
    [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $pattern })
}
function Start-Window([string] $title, [string] $command, [string] $directory) {
    Start-Process powershell -WindowStyle Minimized -WorkingDirectory $directory `
        -ArgumentList '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle = '$title'; $command"
}

Write-Host '1/4 Infrastructure (Docker)…'
docker info *> $null; if ($LASTEXITCODE -ne 0) { throw 'Démarrez Docker Desktop puis relancez ce script.' }
Start-Container 'nexora-mongo' 'mongo:6.0' @('-p', '127.0.0.1:27019:27019', '-v', 'nexora-mongo-data:/data/db', '--', '--replSet', 'nexora', '--port', '27019', '--bind_ip_all')
Start-Container 'nexora-redis' 'redis:7-alpine' @('-p', '127.0.0.1:6379:6379')
Start-Container 'mailpit' 'axllent/mailpit:v1.20' @('-p', '127.0.0.1:8025:8025', '-p', '127.0.0.1:1025:1025')
Wait-Port 27019 'MongoDB'; Wait-Port 6379 'Redis'; Wait-Port 1025 'Mailpit'
& $python (Join-Path $root 'scripts\init_mongo.py'); if ($LASTEXITCODE -ne 0) { throw 'Initialisation MongoDB interrompue.' }

Write-Host '2/4 Base de données à jour…'
& $python (Join-Path $backend 'manage.py') migrate --noinput | Select-Object -Last 1

Write-Host '3/4 Application…'
if (-not (Test-Port 8000)) { Start-Window 'Hub — Django' "& '$python' manage.py runserver 127.0.0.1:8000" $backend }
if (-not (Test-Process 'celery.*-A config worker')) { Start-Window 'Hub — Celery (IA)' "& '$celery' -A config worker --pool=solo --loglevel=info" $backend }
if (-not (Test-Process 'process_course_jobs')) { Start-Window 'Hub — cours (PDF, Whisper)' "& '$python' manage.py process_course_jobs --sleep 2" $backend }
if (-not (Test-Port 5173)) { Start-Window 'Hub — Vite' 'npm run dev' $frontend }
if (-not (Test-Port 11434)) { Write-Host '   Ollama n’est pas lancé : le secours IA local sera indisponible (Gemini reste utilisé).' -ForegroundColor Yellow }

Write-Host '4/4 Vérification…'
Wait-Port 8000 'Django'; Wait-Port 5173 'Vite'
for ($i = 0; $i -lt 30; $i++) {
    try { $health = Invoke-RestMethod 'http://127.0.0.1:5173/api/health/' -TimeoutSec 3; if ($health.status -eq 'ok') { break } } catch { }
    Start-Sleep -Seconds 1
}
if ($health.status -ne 'ok') { throw 'L’API ne répond pas : regardez la fenêtre « Hub — Django ».' }
Write-Host ''
Write-Host 'Hub Éducatif prêt.' -ForegroundColor Green
Write-Host '  Application   : http://localhost:5173'
Write-Host '  Emails (démo) : http://localhost:8025'
Write-Host '  Comptes       : admin / enseignant / etudiant @demo.nexora.test — mot de passe Nexora-Test-2026'
