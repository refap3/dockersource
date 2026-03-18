@echo off
:: Sudoku Tutor — launcher (Windows)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No virtual environment found. Run install.bat first.
    exit /b 1
)

.venv\Scripts\python sudoku_gui.py %*
