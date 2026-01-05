<#
Publish AuraNexus repository to GitHub helper.

Requirements:
- `git` installed and on PATH
- (optional but recommended) `gh` (GitHub CLI) configured with `gh auth login`

Usage examples:
  # Create a public repo named AuraNexus and push
  powershell -ExecutionPolicy Bypass -File scripts\publish_repo.ps1 -Name AuraNexus -Public

  # Create a private repo
  powershell -ExecutionPolicy Bypass -File scripts\publish_repo.ps1 -Name AuraNexus -Private

This script will:
- initialize git if needed
- create an initial commit (if none exists)
- create a GitHub repo using `gh` if available, otherwise print the git commands to run manually
- push to `origin` remote
#>

param(
    [string]$Name = "AuraNexus",
    [switch]$Private,
    [switch]$DryRun
)

function Exec($cmd) { Write-Host "+ $cmd"; if (-not $DryRun) { iex $cmd } }

Write-Host "Publishing repository: $Name"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git not found on PATH. Install Git and re-run."
    exit 2
}

$root = Resolve-Path .
Write-Host "Repository root: $root"

# Initialize git if no .git
if (-not (Test-Path .git)) {
    Exec 'git init'
}

# Ensure .gitignore exists
if (-not (Test-Path .gitignore)) {
    @('.venv/', 'node_modules/', 'dist/', '*.pyc', '__pycache__/') | Set-Content .gitignore
    Exec 'git add .gitignore'
}

# Make initial commit if none
if (-not (git rev-parse --is-inside-work-tree 2>$null)) {
    Write-Error "Not a git repository after init. Aborting."
    exit 3
}

$hasCommit = (git rev-parse --verify HEAD 2>$null) -ne $null
if (-not $hasCommit) {
    Exec 'git add -A'
    Exec 'git commit -m "Initial commit: AuraNexus scaffold"'
}

# Create remote via gh if available
if (Get-Command gh -ErrorAction SilentlyContinue) {
    $vis = $Private.IsPresent ? '--private' : '--public'
    Exec "gh repo create $Name $vis --source . --remote origin --push"
    Write-Host "Repository created and pushed (via gh)."
} else {
    Write-Warning "GitHub CLI (gh) not found. Run the following manually to create a remote and push:"
    Write-Host "  git remote add origin git@github.com:<your-user>/$Name.git"
    Write-Host "  git push -u origin main"
}

Write-Host "Done."
