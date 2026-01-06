# Aura Nexus Launcher
# Ensures venv, installs dependencies if missing, then launches.

$ErrorActionPreference = "Stop"
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
$venvPython   = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$appFile      = Join-Path $PSScriptRoot "chat_launcher.py"

if (-not (Test-Path $venvActivate)) {
  Write-Host "[Aura Nexus] Creating virtual environment..." -ForegroundColor Cyan
  py -m venv .venv
}

& $venvActivate

if (-not (Test-Path $appFile)) {
  Write-Host "Main file not found: $appFile" -ForegroundColor Red
  Write-Host "Looking for chat_launcher.py..." -ForegroundColor Yellow
  exit 1
}

Write-Host "[Aura Nexus] Checking dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip | Out-Null
# Install core (pure-Python) requirements first
try {
    & $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt") | Out-Null
} catch {
    Write-Warning "Failed to install core requirements: $_"
}
# Attempt optional (native build) requirements but do not fail the launch if they don't build
$optionalReq = (Join-Path $PSScriptRoot "requirements-optional.txt")
if (Test-Path $optionalReq) {
    try {
        Write-Host "[Aura Nexus] Installing optional native requirements (may require build tools)..." -ForegroundColor Yellow
        & $venvPython -m pip install -r $optionalReq | Out-Null
    } catch {
        Write-Warning "Optional native requirements failed to install; continuing without local GGUF support."
    }
}

Write-Host "[Aura Nexus] Launching UI..." -ForegroundColor Green
& $venvPython $appFile
