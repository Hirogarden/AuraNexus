# Build AuraNexus Launcher as standalone .exe
# Requires PyInstaller: pip install pyinstaller

param(
    [string]$OutputName = "AuraNexusLauncher",
    [string]$Icon = "assets\icon.ico"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Building AuraNexus Launcher ===" -ForegroundColor Cyan

# Check if virtual environment is activated
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
    Write-Host "Using virtual environment Python" -ForegroundColor Green
} else {
    $python = "python"
    Write-Host "Using system Python" -ForegroundColor Yellow
}

# Check PyInstaller
Write-Host "`nChecking PyInstaller..."
& $python -m pip show pyinstaller | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    & $python -m pip install pyinstaller
}

# Build arguments
$buildArgs = @(
    "launcher\launcher.py",
    "--onefile",
    "--windowed",
    "--name", $OutputName,
    "--add-data", "launcher;launcher",
    "--hidden-import", "PySide6",
    "--hidden-import", "requests",
    "--hidden-import", "launcher.updater",
    "--hidden-import", "launcher.docker_manager",
    "--hidden-import", "launcher.config",
    "--clean"
)

# Add icon if it exists
if (Test-Path $Icon) {
    $buildArgs += @("-i", $Icon)
    Write-Host "Using icon: $Icon" -ForegroundColor Green
} else {
    Write-Host "Icon not found: $Icon (continuing without icon)" -ForegroundColor Yellow
}

# Run PyInstaller
Write-Host "`nBuilding executable..."
& $python -m PyInstaller @buildArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Build Successful! ===" -ForegroundColor Green
    Write-Host "Executable: dist\$OutputName.exe"
    
    # Show file size
    $exePath = "dist\$OutputName.exe"
    if (Test-Path $exePath) {
        $size = (Get-Item $exePath).Length / 1MB
        Write-Host "File size: $([math]::Round($size, 2)) MB"
    }
} else {
    Write-Host "`n=== Build Failed ===" -ForegroundColor Red
    exit 1
}
