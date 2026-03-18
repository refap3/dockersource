#!/usr/bin/env bash
# Sudoku Tutor — update script (Mac / Linux)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="https://github.com/refap3/claudeCode"
SUBDIR="sudokusolver"

echo "=== Sudoku Tutor — update ==="

# If inside a git repo, pull normally; otherwise re-fetch from GitHub
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$REPO_ROOT" ]]; then
    echo "Pulling latest code ..."
    git -C "$REPO_ROOT" pull
else
    echo "Downloading latest files from GitHub ..."
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/repo" -q
    git -C "$TMP/repo" sparse-checkout set "$SUBDIR" -q
    cp -r "$TMP/repo/$SUBDIR/." "$SCRIPT_DIR/"
    chmod +x "$SCRIPT_DIR/launch.sh" "$SCRIPT_DIR/update.sh"
fi

echo "Updating dependencies ..."
cd "$SCRIPT_DIR"
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

echo "Update complete."
