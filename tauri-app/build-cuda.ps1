# Build AuraNexus with CUDA support
Write-Host "🚀 Building AuraNexus with CUDA GPU acceleration..." -ForegroundColor Cyan

Set-Location "$PSScriptRoot\src-tauri"

# Setup Visual Studio environment
Import-Module "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\" -SkipAutomaticLocation

# Setup environment variables
$env:Path = "$env:USERPROFILE\.cargo\bin;C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin;" + $env:Path
$env:LIBCLANG_PATH = "C:\Program Files\LLVM\bin"
$env:CUDA_PATH = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1"

Write-Host ""
Write-Host "⏳ This will take 10-15 minutes on first build..." -ForegroundColor Yellow
Write-Host ""

# Build release version
cargo build --release

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Build successful!" -ForegroundColor Green
    Write-Host "📦 Executable: .\src-tauri\target\release\auranexus.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To run: cd src-tauri ; .\target\release\auranexus.exe"
} else {
    Write-Host ""
    Write-Host "❌ Build failed" -ForegroundColor Red
}
