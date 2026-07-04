# Bootstrap for Windows.
# Clones this repo (if not already inside it) to %USERPROFILE%\.claude-code-catalog,
# then runs the scanner and the interactive picker.

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/SID-SURANGE/claude-code-catalog.git"
$InstallDir = if ($env:CLAUDE_CODE_CATALOG_HOME) { $env:CLAUDE_CODE_CATALOG_HOME } else { "$HOME\.claude-code-catalog" }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git is required but not found."
    exit 1
}
$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Error "python3 (or python) is required but not found."
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $scriptDir "scan.py")) {
    Set-Location $scriptDir
} else {
    if (Test-Path (Join-Path $InstallDir ".git")) {
        git -C $InstallDir pull --ff-only --quiet
    } else {
        git clone --depth 1 --quiet $RepoUrl $InstallDir
    }
    Set-Location $InstallDir
}

Write-Host "Scanning sources..."
& $python.Source scan.py

Write-Host ""
Write-Host "Launching installer..."
& $python.Source install.py @args
