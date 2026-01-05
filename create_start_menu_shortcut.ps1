param(
  [string]$ExePath = "dist\\AuraNexus.exe",
  [string]$ShortcutName = "Aura Nexus",
  [string]$IconPath = "assets\\aura_nexus.ico"
)

$ErrorActionPreference = "Stop"

function Get-StartMenuPath {
  $base = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
  if (-not (Test-Path $base)) { throw "Start Menu path not found: $base" }
  return $base
}

$startMenu = Get-StartMenuPath
if (-not (Test-Path $ExePath)) { throw "Executable not found: $ExePath" }

$shortcutPath = Join-Path $startMenu ("$ShortcutName.lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Resolve-Path $ExePath).Path
$shortcut.WorkingDirectory = (Split-Path -Parent (Resolve-Path $ExePath).Path)
if (Test-Path $IconPath) { $shortcut.IconLocation = (Resolve-Path $IconPath).Path }
$shortcut.Description = "Launch Aura Nexus"
$shortcut.Save()

Write-Host "Created Start Menu shortcut: $shortcutPath"
