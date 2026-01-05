param(
  [string]$Name = "AuraNexus",
  [string]$Script = "aura_nexus_app.py",
  [string]$Icon = "assets\aura_nexus.ico"
)

$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) { $python = $venvPython } else { $python = "python" }

Write-Host "Using Python: $python"
& $python -m pip show pyinstaller | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Installing PyInstaller..."
  & $python -m pip install pyinstaller | Out-Null
}

# Build onedir (folder) for minimal flicker
$argsDir = @($Script, '--windowed', '--name', $Name, '--onedir')
if (Test-Path $Icon) { $argsDir += @('-i', $Icon) }
Write-Host "Building onedir distribution..."
& $python -m PyInstaller @argsDir
if ($LASTEXITCODE -ne 0) { throw "Onedir build failed" }

# Zip the onedir folder with icon and a tiny README
$distDir = Join-Path $PSScriptRoot "dist\$Name"
if (-not (Test-Path $distDir)) { throw "Missing dist folder: $distDir" }

$zipPath = Join-Path $PSScriptRoot "dist\$Name-onedir.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

# Write README directly into the dist folder for packaging
$readme = @"
Aura Nexus (onedir build)

How to run:
- Open the folder `$Name` inside this zip and run `$Name.exe`.
- This build minimizes console flicker on Windows.

Notes:
- Place `aura_nexus.ico` next to the exe if you want Explorer to show the icon for the folder and shortcuts.
"@
Set-Content -Path (Join-Path $distDir "README.txt") -Value $readme -NoNewline
if (Test-Path $Icon) { Copy-Item -Force $Icon $distDir }

# Small delay to avoid file locks, then compress the whole folder
Start-Sleep -Seconds 2
Compress-Archive -Path $distDir -DestinationPath $zipPath -Force

Write-Host "Publish complete: $zipPath"
