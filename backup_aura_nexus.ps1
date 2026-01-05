# Backs up Aura Nexus workspace and profile to a zip
param(
    [string]$BackupDir = "$env:USERPROFILE\Desktop",
    [string]$ZipName = "AuraNexus_Backup.zip"
)

$ErrorActionPreference = "Stop"

$workspace = "c:\Users\harol\Tie Together"
$profileDir = Join-Path $env:APPDATA "AuraNexus"
$profileJson = Join-Path $profileDir "profile.json"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $BackupDir ($ZipName -replace ".zip$", "_$timestamp.zip")

Write-Host "Backing up workspace and profile to" $zipPath

$items = @()
if (Test-Path $workspace) { $items += $workspace }
if (Test-Path $profileDir) { $items += $profileDir }

if ($items.Count -eq 0) {
    Write-Warning "Nothing to back up. Exiting."
    exit 0
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
# Create zip
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($items[0], $zipPath)
# Append other directories if present
for ($i = 1; $i -lt $items.Count; $i++) {
    $tmp = Join-Path $BackupDir "tmp_$timestamp.zip"
    [System.IO.Compression.ZipFile]::CreateFromDirectory($items[$i], $tmp)
    # Merge: extract tmp into main zip (workaround by re-zip)
    $mergeDir = Join-Path $BackupDir "merge_$timestamp"
    New-Item -ItemType Directory -Force -Path $mergeDir | Out-Null
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $mergeDir)
    [System.IO.Compression.ZipFile]::ExtractToDirectory($tmp, $mergeDir)
    Remove-Item $zipPath -Force
    [System.IO.Compression.ZipFile]::CreateFromDirectory($mergeDir, $zipPath)
    Remove-Item $tmp -Force
    Remove-Item $mergeDir -Recurse -Force
}

Write-Host "Backup complete: $zipPath"