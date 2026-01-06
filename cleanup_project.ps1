# AuraNexus Cleanup Script
# Removes deprecated, duplicate, and unnecessary files

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  AuraNexus Project Cleanup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

$removed = @()
$kept = @()

# === DEPRECATED LAUNCHERS ===
Write-Host "[1/5] Cleaning up deprecated launchers..." -ForegroundColor Yellow

$deprecatedLaunchers = @(
    "ai_launcher.py",           # Just prints error message
    "companion_app.py",         # Legacy shim, unused
    "launch.py"                 # Redundant with chat_launcher.py
)

foreach ($file in $deprecatedLaunchers) {
    if (Test-Path $file) {
        Write-Host "  Removing: $file" -ForegroundColor Red
        Remove-Item $file -Force
        $removed += $file
    }
}

# === OLD TEST FILES (root level) ===
Write-Host "[2/5] Cleaning up scattered test files..." -ForegroundColor Yellow

$oldTests = @(
    "test_all_features.py",
    "test_health_debug.py",
    "test_launcher_integration.py",
    "test_memory_embed.py",
    "test_ui.py",
    "test_upgrades.py",
    "tool_demo.py",
    "interactive_test.py"
)

# Create tests directory if needed
if (-not (Test-Path "tests")) {
    New-Item -ItemType Directory -Path "tests" | Out-Null
    Write-Host "  Created tests/ directory" -ForegroundColor Green
}

foreach ($file in $oldTests) {
    if (Test-Path $file) {
        $newPath = "tests/$file"
        Write-Host "  Moving: $file -> tests/" -ForegroundColor Yellow
        Move-Item $file $newPath -Force
        $kept += "tests/$file"
    }
}

# Keep our important harvest demo
if (Test-Path "test_kobold_harvest.py") {
    Move-Item "test_kobold_harvest.py" "tests/test_kobold_harvest.py" -Force
    Write-Host "  Moving: test_kobold_harvest.py -> tests/" -ForegroundColor Green
    $kept += "tests/test_kobold_harvest.py"
}

# === DUPLICATE RUNNERS ===
Write-Host "[3/5] Cleaning up duplicate PowerShell runners..." -ForegroundColor Yellow

# We have both run_aura_nexus.ps1 and run_auranexus.ps1 (different spelling)
if ((Test-Path "run_aura_nexus.ps1") -and (Test-Path "run_auranexus.ps1")) {
    # Keep the one with underscore (more consistent)
    Write-Host "  Removing duplicate: run_auranexus.ps1 (keeping run_aura_nexus.ps1)" -ForegroundColor Red
    Remove-Item "run_auranexus.ps1" -Force
    $removed += "run_auranexus.ps1"
}

# === OLD TOOLS TEST FILES ===
Write-Host "[4/5] Cleaning up old tool tests..." -ForegroundColor Yellow

$oldToolTests = @(
    "tools/test_api_create.py",      # Old API test
    "tools/test_model_import.py",    # Superseded by v2
    "tools/test_features.py",        # Redundant
    "tools/ollama_repro.log",        # Old logs
    "tools/ollama_stress.log",
    "tools/deploy.log"
)

foreach ($file in $oldToolTests) {
    if (Test-Path $file) {
        Write-Host "  Removing: $file" -ForegroundColor Red
        Remove-Item $file -Force
        $removed += $file
    }
}

# === DEPRECATED APP ===
Write-Host "[5/5] Handling deprecated full app..." -ForegroundColor Yellow

# aura_nexus_app.py is 2220 lines but marked deprecated
# Move to archive for code harvesting
if (-not (Test-Path "archive")) {
    New-Item -ItemType Directory -Path "archive" | Out-Null
    Write-Host "  Created archive/ directory" -ForegroundColor Green
}

if (Test-Path "aura_nexus_app.py") {
    Write-Host "  Archiving: aura_nexus_app.py -> archive/ (for code harvesting)" -ForegroundColor Yellow
    Move-Item "aura_nexus_app.py" "archive/aura_nexus_app.py" -Force
    $kept += "archive/aura_nexus_app.py"
}

# === CLEAN PYCACHE ===
Write-Host ""
Write-Host "Cleaning __pycache__ directories..." -ForegroundColor Yellow

Get-ChildItem -Path . -Recurse -Filter "__pycache__" -Directory | ForEach-Object {
    Write-Host "  Removing: $($_.FullName)" -ForegroundColor DarkGray
    Remove-Item $_.FullName -Recurse -Force
}

# === SUMMARY ===
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Cleanup Summary" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files removed: $($removed.Count)" -ForegroundColor Red
foreach ($file in $removed) {
    Write-Host "  - $file" -ForegroundColor Red
}

Write-Host ""
Write-Host "Files moved/archived: $($kept.Count)" -ForegroundColor Yellow
foreach ($file in $kept) {
    Write-Host "  - $file" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "  Cleanup Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "Project structure cleaned:" -ForegroundColor Green
Write-Host "  Main launcher: chat_launcher.py" -ForegroundColor White
Write-Host "  Main script: run_aura_nexus.ps1" -ForegroundColor White
Write-Host "  Core code: src/" -ForegroundColor White
Write-Host "  Tests: tests/" -ForegroundColor White
Write-Host "  Archive: archive/ (old code for harvesting)" -ForegroundColor White
Write-Host ""
