param(
  [string]$ExePath = "dist\\AuraNexus.exe",
  [string]$ShortcutName = "Aura Nexus",
  [string]$IconPath = "assets\\aura_nexus.ico"
)

$ErrorActionPreference = "Stop"

function Get-DesktopPath {
  try {
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    if (-not $desktop) { $desktop = $shell.SpecialFolders.Item('Desktop') }
    return $desktop
  } catch {
    return [Environment]::GetFolderPath('Desktop')
  }
}

$desktop = Get-DesktopPath
if (-not (Test-Path $ExePath)) { throw "Executable not found: $ExePath" }

$shortcutPath = Join-Path $desktop ("$ShortcutName.lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Resolve-Path $ExePath).Path
$shortcut.WorkingDirectory = (Split-Path -Parent (Resolve-Path $ExePath).Path)
if (Test-Path $IconPath) { $shortcut.IconLocation = (Resolve-Path $IconPath).Path }
$shortcut.Description = "Launch Aura Nexus"
$shortcut.Save()

Write-Host "Created shortcut: $shortcutPath"
