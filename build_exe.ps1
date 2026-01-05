param(
  [string]$Script = "aura_nexus_app.py",
  [string]$Name = "AuraNexus",
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

Write-Host "Building $Script as $Name.exe"
$args = @($Script, '--onefile', '--windowed', '--name', $Name)
if (Test-Path $Icon) { $args += @('-i', $Icon) }
& $python -m PyInstaller @args
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

Write-Host "Build complete. See dist/$Name.exe"
