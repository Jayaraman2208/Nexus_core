<#
.SYNOPSIS
    NexusCore setup script — installs all backend + frontend dependencies and
    initializes the project for local development on Windows.

.NOTES
    Run from the repository root:  .\setup.ps1
    Requires: Python 3.11+, Node.js 20+, and (optionally) Docker Desktop for
    Postgres/Redis. If Docker isn't available, the script falls back to SQLite
    and asks you to run Redis separately (required for Celery + WebSockets).
#>

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# 0. Pre-flight checks
# ---------------------------------------------------------------------------
Write-Step "Checking prerequisites"

if (-not (Test-Command "python")) {
    Write-Error "Python was not found on PATH. Install Python 3.11+ from https://www.python.org/downloads/ and re-run this script."
    exit 1
}
if (-not (Test-Command "node")) {
    Write-Error "Node.js was not found on PATH. Install Node.js 20 LTS from https://nodejs.org/ and re-run this script."
    exit 1
}

$pythonVersion = (python --version)
$nodeVersion = (node --version)
Write-Host "Found $pythonVersion"
Write-Host "Found Node $nodeVersion"

$dockerAvailable = Test-Command "docker"
if ($dockerAvailable) {
    Write-Host "Docker detected — Postgres and Redis can be started automatically."
} else {
    Write-Host "Docker not found — will fall back to SQLite and expect Redis to be started manually." -ForegroundColor Yellow
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

# ---------------------------------------------------------------------------
# 1. Backend: virtual environment + Python dependencies
# ---------------------------------------------------------------------------
Write-Step "Creating Python virtual environment"
Set-Location $backendDir

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

Write-Step "Upgrading pip and installing backend dependencies"
python -m pip install --upgrade pip
pip install -r requirements.txt

# All backend dependencies (installed above from requirements.txt), listed here for reference:
#   Django, djangorestframework, djangorestframework-simplejwt, django-cors-headers,
#   django-filter, django-fsm, channels, channels-redis, daphne, celery, redis,
#   django-celery-results, psycopg2-binary, python-dotenv, requests, gunicorn, whitenoise

Write-Step "Setting up environment file"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env from .env.example — edit it to set a real DJANGO_SECRET_KEY, etc." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 2. Infrastructure: Postgres + Redis (via Docker) or SQLite fallback
# ---------------------------------------------------------------------------
if ($dockerAvailable) {
    Write-Step "Starting Postgres and Redis via Docker"
    Set-Location $repoRoot
    docker compose up -d postgres redis
    Set-Location $backendDir
    (Get-Content ".env") -replace '^USE_SQLITE=.*', 'USE_SQLITE=False' | Set-Content ".env"
} else {
    Write-Host "Skipping Postgres/Redis containers — using SQLite for the database." -ForegroundColor Yellow
    Write-Host "You must install and run Redis yourself for Celery + WebSockets to work (e.g. via WSL or Memurai for Windows)." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 3. Database migrations + superuser
# ---------------------------------------------------------------------------
Write-Step "Running database migrations"
python manage.py makemigrations core
python manage.py migrate

Write-Step "Create an admin (superuser) account"
$createSuperuser = Read-Host "Create a superuser now? (y/n)"
if ($createSuperuser -eq "y") {
    python manage.py createsuperuser
}

# ---------------------------------------------------------------------------
# 4. Frontend: Node dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing frontend dependencies"
Set-Location $frontendDir
npm install

# ---------------------------------------------------------------------------
# 5. Done
# ---------------------------------------------------------------------------
Set-Location $repoRoot
Write-Step "Setup complete!"
Write-Host @"

Next steps — open three terminals:

  1) Backend API + WebSockets:
       cd backend
       .\.venv\Scripts\Activate.ps1
       daphne -b 0.0.0.0 -p 8000 nexuscore.asgi:application

  2) Celery worker (background provisioning tasks):
       cd backend
       .\.venv\Scripts\Activate.ps1
       celery -A nexuscore worker -l info

  3) Frontend dev server:
       cd frontend
       npm run dev

Then open http://localhost:5173 and log in with the superuser you created.

Alternatively, once Docker Desktop is installed, run the whole stack with:
       docker compose up --build
"@ -ForegroundColor Green
