param(
  [string]$ModelPath = "",
  [string]$Name = "user-model",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not $ModelPath) {
  Write-Host "Usage: .\tools\import_to_ollama.ps1 -ModelPath <path to gguf> -Name <model-name>"
  exit 1
}
$ModelPath = (Resolve-Path $ModelPath).Path
if (-not (Test-Path $ModelPath)) {
  Write-Host "Model not found: $ModelPath"
  exit 2
}

# Check if ollama is installed
$oll = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $oll) {
  Write-Host "ollama command not found. Please install Ollama from https://ollama.ai and ensure it's in PATH."
  exit 3
}

# Create temporary folder for Modelfile
$tmp = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tmp | Out-Null
$mf = Join-Path $tmp "Modelfile"

# Write a simple Modelfile for gguf local path
$modelfileContents = @"
FROM $ModelPath
TEMPLATE "[INST] {{ .Prompt }} [/INST]"
PARAMETER stop "[INST]"
PARAMETER stop "<<SYS>>"
"@ -replace "\r?\n", "`n"

$modelfileContents | Set-Content -Path $mf -Encoding UTF8

Write-Host "Creating Ollama model named: $Name from: $ModelPath"

# Run ollama create -f Modelfile
$cmd = "ollama create $Name -f '$mf'"
Write-Host "Running: $cmd"

try {
  if ($Force) {
    # Delete existing model if any (no force flag supported; ignore errors)
    try {
      & ollama rm $Name 2>$null | Out-Null
    } catch {
      # ignore
    }
  }
  & ollama create $Name --file $mf
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Model created successfully: $Name"
    exit 0
  } else {
    Write-Host "Model creation failed. Exit code: $LASTEXITCODE"
    exit $LASTEXITCODE
  }
} catch {
  Write-Host "Error creating model: $_"
  exit 4
} finally {
  # Clean up temp files but keep them if creation failed
  if ($LASTEXITCODE -eq 0) {
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
  } else {
    Write-Host "Modelfile retained at: $mf for inspection"
  }
}
