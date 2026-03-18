# Sudoku Tutor — installer (Windows PowerShell)
#
# Fresh install (one line, no repo needed):
#   powershell -ExecutionPolicy Bypass -Command "iex (irm 'https://raw.githubusercontent.com/refap3/claudeCode/main/sudokusolver/install.ps1')"
#
# Already have the repo:
#   powershell -ExecutionPolicy Bypass .\sudokusolver\install.ps1   # from repo root
#   powershell -ExecutionPolicy Bypass .\install.ps1                # from sudokusolver\
#
# Wipe and reinstall:
#   Remove-Item -Recurse -Force ~/sudoku-tutor
#   powershell -ExecutionPolicy Bypass -Command "iex (irm 'https://raw.githubusercontent.com/refap3/claudeCode/main/sudokusolver/install.ps1')"
$ErrorActionPreference = "Stop"

$REPO   = "https://github.com/refap3/claudeCode"
$SUBDIR = "sudokusolver"

# ── Detect local vs fresh (irm) mode ─────────────────────────────────────────
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { "" }
if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "sudoku_gui.py"))) {
    $Fresh = $false
    $Dest  = $ScriptDir
} else {
    $Fresh = $true
    $Dest  = if ($env:SUDOKU_DIR) { $env:SUDOKU_DIR } else { Join-Path $HOME "sudoku-tutor" }
}

Write-Host "=== Sudoku Tutor — install ===" -ForegroundColor Cyan

if ($Fresh) {
    if (Test-Path (Join-Path $Dest "sudoku_gui.py")) {
        Write-Host "Already installed at $Dest — run update.bat to refresh."
        exit 0
    }
    Write-Host "Installing to $Dest ..."
    Write-Host "Cloning from GitHub (sudokusolver only) ..."
    $Tmp = Join-Path $env:TEMP "sudoku_install_$(New-Guid)"
    try {
        git clone --depth 1 --filter=blob:none --sparse $REPO "$Tmp\repo" -q 2>&1 | Out-Null
        git -C "$Tmp\repo" sparse-checkout set $SUBDIR -q 2>&1 | Out-Null
        New-Item -ItemType Directory -Force $Dest | Out-Null
        Copy-Item "$Tmp\repo\$SUBDIR\*" -Destination $Dest -Recurse -Force
    } finally {
        Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
    }
}

Set-Location $Dest

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: python not found. Install Python 3.8+ from python.org" -ForegroundColor Red
    exit 1
}

Write-Host "Creating virtual environment ..."
python -m venv .venv
Write-Host "Installing dependencies ..."
.\.venv\Scripts\pip install --upgrade pip -q
.\.venv\Scripts\pip install -r requirements.txt -q

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "  Launch: $Dest\launch.bat"
Write-Host "  Update: $Dest\update.bat"
