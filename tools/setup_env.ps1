# Creates or refreshes the Python virtual environment and installs dependencies
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$activate = Join-Path $venv "Scripts\Activate.ps1"
$python = Join-Path $venv "Scripts\python.exe"
$req = Join-Path $root "requirements.txt"
$reqLock = Join-Path $root "requirements.lock"

if (-not (Test-Path $activate)) {
  Write-Host "[setup] Creating virtual environment..." -ForegroundColor Cyan
  py -m venv $venv
}

& $activate

Write-Host "[setup] Upgrading pip and installing requirements..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r $req

if (Test-Path $reqLock) {
  Write-Host "[setup] Installing locked extras..." -ForegroundColor Cyan
  & $python -m pip install -r $reqLock
}

Write-Host "[setup] Done. Use run_aura_nexus.ps1 to start." -ForegroundColor Green
