#!/usr/bin/env bash
# Sudoku Tutor — launcher (Mac / Linux)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .venv/bin/python ]; then
    echo "No virtual environment found. Run install.sh first."
    exit 1
fi

exec .venv/bin/python sudoku_gui.py "$@"
