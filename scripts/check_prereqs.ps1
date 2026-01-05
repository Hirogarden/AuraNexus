<#
Simple Windows PowerShell prereq checker for AuraNexus.
Run this before attempting to `npm install` or start the Electron app.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\check_prereqs.ps1

It checks for `node`, `npm`, `python`, and `pip` on PATH and prints guidance.
#>

function Check-Command($displayName, [string[]]$candidates) {
    Write-Host "Checking $displayName..." -NoNewline
    $found = $false
    foreach ($c in $candidates) {
        # Try Get-Command first
        if (Get-Command $c -ErrorAction SilentlyContinue) { $found = $true; break }
        # Fallback to where.exe for Windows PATH lookup
        try {
            $out = & where.exe $c 2>$null
            if ($out) { $found = $true; break }
        } catch { }
    }
    if ($found) { Write-Host " OK" -ForegroundColor Green; return $true }
    Write-Host " MISSING" -ForegroundColor Yellow; return $false
}

$allOk = $true
if (-not (Check-Command 'Node.js' @('node','node.exe'))) { $allOk = $false }
if (-not (Check-Command 'npm' @('npm','npm.cmd','npm.exe'))) { $allOk = $false }
if (-not (Check-Command 'Python' @('python','python3','python.exe'))) { $allOk = $false }
if (-not (Check-Command 'pip' @('pip','pip3','pip.exe'))) { $allOk = $false }

if (-not $allOk) {
    Write-Host "`nOne or more prerequisites are missing. Suggestions:" -ForegroundColor Cyan
    Write-Host '- Install Node.js LTS: https://nodejs.org/' -ForegroundColor White
    Write-Host '  You can install via winget: winget install OpenJS.NodeJS.LTS' -ForegroundColor Gray
    Write-Host '- Install Python 3: https://www.python.org/downloads/' -ForegroundColor White
    Write-Host "  Ensure 'Add Python to PATH' is enabled during install." -ForegroundColor Gray
    Write-Host '- Re-open the terminal after installing so PATH changes take effect.' -ForegroundColor Gray
    exit 2
} else {
    Write-Host "`nAll prerequisites appear to be installed." -ForegroundColor Green
    exit 0
}
