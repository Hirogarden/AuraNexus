<#
AuraNexus Windows development setup script.
Run from the repository root in PowerShell (use an elevated shell if installing system packages):

  powershell -ExecutionPolicy Bypass -File scripts\dev_setup.ps1

What it does:
 - Runs a prereq check
 - Creates and activates a Python venv in `app\.venv` and installs Python deps
 - Runs `npm install` in `ui/electron`
#>

Write-Host "Running AuraNexus dev setup..." -ForegroundColor Cyan

# Resolve repository root (one level up from this script)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir '..')
Push-Location $repoRoot

Write-Host "Checking prerequisites..." -ForegroundColor Cyan
try {
    $checkScript = Join-Path $repoRoot 'scripts\check_prereqs.ps1'
    if (-not (Test-Path $checkScript)) { throw "Prereq script not found: $checkScript" }
    & powershell -ExecutionPolicy Bypass -File $checkScript
} catch {
    Write-Error "Prereq check failed. Install missing prerequisites and re-run this script.: $_"; exit 2
}

Write-Host "Setting up Python virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path app\.venv)) {
    python -m venv app\.venv
}

Write-Host "Activating venv and installing Python requirements..." -ForegroundColor Cyan
& cmd /c "app\.venv\Scripts\activate && pip install -r app\requirements.txt"

Write-Host "Installing Electron UI dependencies..." -ForegroundColor Cyan
$uiElectronPath = Join-Path $repoRoot 'ui\electron'
if (Test-Path $uiElectronPath) {
    Push-Location $uiElectronPath
    if (Test-Path package.json) {
    # Run the Node prereq checker first (PowerShell-compatible)
    try {
        & node ./scripts/check_prereqs.js
        if ($LASTEXITCODE -ne 0) { throw "Node prereq check failed (non-zero exit)." }
    } catch {
        Write-Error "Node prereq check failed: $_"
        Pop-Location
        exit 3
    }
        npm install
    } else {
        Write-Warning 'ui\electron/package.json not found - skipping npm install'
    }
    Pop-Location
} else {
    Write-Warning 'ui\electron folder not found - skipping npm install'
}

Write-Host 'Dev setup complete. To run the app, activate the venv and start the Electron app:' -ForegroundColor Green
Write-Host '  In cmd.exe, run:' -ForegroundColor Yellow
Write-Host '    app\.venv\Scripts\activate' -ForegroundColor Yellow
Write-Host '    python app\aura_launcher.py start-all' -ForegroundColor Yellow
Write-Host '  (then in a separate shell) in ui\electron: npm run start' -ForegroundColor Yellow

Pop-Location
