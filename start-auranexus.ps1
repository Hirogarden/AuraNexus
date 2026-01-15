# AuraNexus Unified Launcher
# Starts frontend dev server, Python backend, and Tauri UI

Write-Host "Starting AuraNexus..." -ForegroundColor Cyan

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Refresh PATH to include Rust
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "Step 1: Starting Node dev server (port 1420)..." -ForegroundColor Yellow
$nodeProcess = Start-Process -FilePath "node" -ArgumentList "tauri-app/ui/server.js" -PassThru -NoNewWindow
Start-Sleep -Seconds 2

# Check if Node server is running
try {
    $response = Invoke-WebRequest -Uri "http://localhost:1420/" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "[OK] Node dev server running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node dev server failed to start" -ForegroundColor Red
    exit 1
}

Write-Host "Step 2: Starting Python backend (port 8000)..." -ForegroundColor Yellow
Write-Host "   (This may take 30-60 seconds to load ML models...)" -ForegroundColor Gray
$pythonProcess = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m","electron-app.backend.core_app" -PassThru -NoNewWindow

# Wait for backend with timeout
$timeout = 120 # 2 minutes for ML model loading
$elapsed = 0
$backendReady = $false

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "[OK] Python backend running" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "   Waiting for backend... ($elapsed seconds)" -ForegroundColor Gray
    }
}

if (-not $backendReady) {
    Write-Host "[WARN] Backend took too long to start, but continuing..." -ForegroundColor Yellow
    Write-Host "   You can check the backend status in the UI" -ForegroundColor Gray
}

Write-Host "Step 3: Starting Tauri UI..." -ForegroundColor Yellow
Set-Location tauri-app
npm run dev

# Cleanup on exit
Write-Host "`nShutting down..." -ForegroundColor Cyan
if ($nodeProcess -and !$nodeProcess.HasExited) {
    Stop-Process -Id $nodeProcess.Id -Force -ErrorAction SilentlyContinue
}
if ($pythonProcess -and !$pythonProcess.HasExited) {
    Stop-Process -Id $pythonProcess.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "[OK] Cleanup complete" -ForegroundColor Green
