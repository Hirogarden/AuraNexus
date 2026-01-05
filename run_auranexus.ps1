# AuraNexus - Application Launcher Script
# This script sets up the environment and runs AuraNexus

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AuraNexus - Unified Application" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $scriptDir ".venv"
$activatePath = Join-Path $venvPath "Scripts\Activate.ps1"

# Check if venv exists
if (-not (Test-Path $venvPath)) {
    Write-Host "ERROR: Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the setup first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Gray
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Gray
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
& $activatePath

Write-Host "Starting AuraNexus..." -ForegroundColor Green
Write-Host ""

# Run the application
python (Join-Path $scriptDir "launch.py")

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Application exited with code $LASTEXITCODE" -ForegroundColor Red
    pause
}
