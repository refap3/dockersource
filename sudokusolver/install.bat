@echo off
:: Sudoku Tutor — one-line installer (Windows)
:: Usage (from repo root):  sudokusolver\install.bat
:: Usage (from this dir):   install.bat
setlocal

cd /d "%~dp0"
echo === Sudoku Tutor — install ===

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found. Install Python 3.8+ from python.org and try again.
    exit /b 1
)

echo Creating virtual environment in .venv\ ...
python -m venv .venv

echo Installing dependencies ...
.venv\Scripts\pip install --upgrade pip -q
.venv\Scripts\pip install -r requirements.txt -q

echo.
echo Done!  Run:  sudokusolver\launch.bat
echo        or:   launch.bat  (from this directory)
