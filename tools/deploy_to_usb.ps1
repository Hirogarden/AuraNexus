param(
    [string]$Target = "D:\AuraNexus",
    [switch]$Mirror,
    [switch]$NoBackup,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$Log
)

# Deployment script: backs up existing target (unless -NoBackup), then copies current workspace to target.
# Usage examples:
#   .\deploy_to_usb.ps1                      # copy to D:\AuraNexus (no mirror / no delete)
#   .\deploy_to_usb.ps1 -Target D:\Working -Mirror   # mirror (delete extra files)
#   .\deploy_to_usb.ps1 -NoBackup -Force     # skip backup and don't prompt

Set-StrictMode -Version Latest

$src = (Resolve-Path "$(Split-Path -Path $MyInvocation.MyCommand.Path -Parent)\..\").Path
# Normalize source to workspace root
try {
    $src = (Get-Item $src).FullName
} catch {
    Write-Error "Failed to determine workspace root: $src"
    exit 1
}

Write-Host "Source: $src"
Write-Host "Target: $Target"

# Safety: confirm target
if (-not $Force) {
    if (Test-Path $Target) {
        $ans = Read-Host ("Target exists. Proceed with deployment to " + $Target + "? (yes/no)")
        if ($ans -ne 'yes') {
            Write-Host "Aborting by user request."
            exit 0
        }
    } else {
        $ans = Read-Host ("Target does not exist. Create " + $Target + "? (yes/no)")
        if ($ans -ne 'yes') {
            Write-Host "Aborting by user request."
            exit 0
        }
    }
}

# Ensure target exists
if (-not (Test-Path $Target)) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
}

# Backup existing target unless NoBackup (skip when DryRun)
if (-not $DryRun -and -not $NoBackup -and (Test-Path $Target) -and (Get-ChildItem -Path $Target -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {
    try {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $zip = Join-Path (Split-Path $Target -Parent) "$(Split-Path $Target -Leaf)_backup_$stamp.zip"
        Write-Host "Creating compressed backup: $zip"
        Compress-Archive -Path "$Target\*" -DestinationPath $zip -Force
        Write-Host "Backup created: $zip"
    } catch {
        Write-Warning "Backup failed: $_"
        if (-not $Force) {
            Write-Host "Aborting due to backup failure."; exit 1
        }
    }
} else {
    if ($DryRun) { Write-Host "Dry run: skipping backup creation." }
}

# Exclude patterns
$excludeDirs = @('.venv', 'build', 'dist', '__pycache__', '.git')
$excludeFiles = @('*.pyc', '*.log')

# Build robocopy arguments
$robocopyArgs = @()
if ($Mirror) { $robocopyArgs += '/MIR' } else { $robocopyArgs += '/E' }
$robocopyArgs += '/COPY:DAT'
$robocopyArgs += '/R:2'  # retries
$robocopyArgs += '/W:5'  # wait seconds
$robocopyArgs += '/V'    # verbose
$robocopyArgs += '/NFL'  # no file list
$robocopyArgs += '/NDL'  # no dir list

foreach ($d in $excludeDirs) { $robocopyArgs += ('/XD', (Join-Path $src $d)) }
foreach ($f in $excludeFiles) { $robocopyArgs += ('/XF', $f) }

Write-Host "Running robocopy with args: $robocopyArgs"

if ($DryRun) {
    Write-Host "DRY RUN: robocopy will run with /L (no files copied)."
    # add the /L switch to preview
    $robocopyArgs += '/L'
}

# Execute robocopy (optionally log output)
if ($Log) {
    $deployLog = Join-Path $src 'tools\deploy.log'
    Write-Host "Logging robocopy output to: $deployLog"
    & robocopy $src $Target $robocopyArgs | Tee-Object -FilePath $deployLog
} else {
    & robocopy $src $Target $robocopyArgs
}

$exitCode = $LASTEXITCODE
if ($exitCode -ge 8) {
    Write-Warning "Robocopy reported errors (exit code $exitCode). Check output above."
} else {
    Write-Host "Robocopy completed with exit code $exitCode"
}


# Write deployment marker (skip on DryRun)
if (-not $DryRun) {
    try {
        $marker = @{ deployed_from = $src; deployed_at = (Get-Date).ToString('o') }
        $marker | ConvertTo-Json | Out-File -FilePath (Join-Path $Target 'DEPLOYMENT_INFO.json') -Encoding utf8
        Write-Host "Wrote DEPLOYMENT_INFO.json to target"
    } catch {
        Write-Warning "Failed to write deployment marker: $_"
    }
} else {
    Write-Host "Dry run: not writing DEPLOYMENT_INFO.json"
}

Write-Host "Deployment complete."