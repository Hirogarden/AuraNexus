# Restores Aura Nexus environment on a fresh Windows install
param(
    [string]$ZipPath,
    [string]$TargetDir = "c:\Users\harol\Tie Together"
)

$ErrorActionPreference = "Stop"

if (-not $ZipPath) {
    Write-Error "Provide -ZipPath to backup zip"
    exit 1
}

# Ensure target dir
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem
$extractDir = Join-Path $TargetDir "_restore"
if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $extractDir)

# Move workspace content back
$possibleWorkspace = Join-Path $extractDir "Tie Together"
if (Test-Path $possibleWorkspace) {
    Copy-Item -Recurse -Force (Join-Path $possibleWorkspace "*") $TargetDir
} else {
    # Fall back: copy everything
    Copy-Item -Recurse -Force (Join-Path $extractDir "*") $TargetDir
}

# Restore profile to %APPDATA%\AuraNexus
$profileSrc = Join-Path $extractDir "AuraNexus"
$profileDst = Join-Path $env:APPDATA "AuraNexus"
if (Test-Path $profileSrc) {
    New-Item -ItemType Directory -Force -Path $profileDst | Out-Null
    Copy-Item -Recurse -Force (Join-Path $profileSrc "*") $profileDst
}

# Recreate Python env and install requirements
$venvPath = Join-Path $TargetDir ".venv"
Write-Host "Creating virtual environment at" $venvPath
python -m venv $venvPath
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
& $activate

$req = Join-Path $TargetDir "requirements.txt"
if (Test-Path $req) {
    Write-Host "Installing requirements..."
    pip install --upgrade pip
    pip install -r $req
} else {
    Write-Warning "No requirements.txt found; skipping."
}

Write-Host "Restore complete. Run with: .\\run_aura_nexus.ps1"