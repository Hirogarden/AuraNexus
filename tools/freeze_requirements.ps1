# Freezes exact dependency versions to requirements.lock for reproducibility
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$lockFile = Join-Path $root "requirements.lock"

if (-not (Test-Path (Join-Path $venv "Scripts\Activate.ps1"))) {
  Write-Error "Virtual environment not found. Run tools/setup_env.ps1 first."; exit 1
}

Write-Host "[freeze] Generating lockfile at $lockFile" -ForegroundColor Cyan
& $python -m pip freeze | Set-Content -Path $lockFile -Encoding UTF8
Write-Host "[freeze] Done." -ForegroundColor Green
