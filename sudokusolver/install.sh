#!/usr/bin/env bash
# Sudoku Tutor — installer (Mac / Linux)
#
# Fresh install (one line, no repo needed):
#   curl -fsSL https://raw.githubusercontent.com/refap3/claudeCode/main/sudokusolver/install.sh | bash
#
# Already have the repo:
#   bash sudokusolver/install.sh      # from repo root
#   bash install.sh                   # from sudokusolver/
#
# Wipe and reinstall:
#   rm -rf ~/sudoku-tutor
#   curl -fsSL https://raw.githubusercontent.com/refap3/claudeCode/main/sudokusolver/install.sh | bash
set -euo pipefail

REPO="https://github.com/refap3/claudeCode"
SUBDIR="sudokusolver"

# ── Detect local vs fresh (curl) mode ────────────────────────────────────────
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" != "bash" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
fi

if [[ -n "$SCRIPT_DIR" ]] && [[ -f "$SCRIPT_DIR/sudoku_gui.py" ]]; then
    FRESH=false
    DEST="$SCRIPT_DIR"
else
    FRESH=true
    DEST="${SUDOKU_DIR:-$HOME/sudoku-tutor}"
fi

echo "=== Sudoku Tutor — install ==="

if [[ "$FRESH" == true ]]; then
    if [[ -f "$DEST/sudoku_gui.py" ]]; then
        echo "Already installed at $DEST — run update.sh to refresh."
        exit 0
    fi
    echo "Installing to $DEST ..."
    echo "Cloning from GitHub (sudokusolver only) ..."
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/repo" -q
    git -C "$TMP/repo" sparse-checkout set "$SUBDIR" -q
    mkdir -p "$DEST"
    cp -r "$TMP/repo/$SUBDIR/." "$DEST/"
fi

cd "$DEST"

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+ and try again." >&2
    exit 1
fi

echo "Creating virtual environment ..."
python3 -m venv .venv
echo "Installing dependencies ..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
chmod +x launch.sh update.sh

# Launcher scripts (always written so re-running repairs missing launchers)
BIN="${SUDOKU_BIN:-$HOME/.local/bin}"
mkdir -p "$BIN"

cat > "$BIN/sudoku" <<EOF
#!/usr/bin/env bash
"$DEST/.venv/bin/python" "$DEST/sudoku_gui.py" "\$@" > /dev/null 2>&1 &
disown
EOF
chmod +x "$BIN/sudoku"

cat > "$BIN/sudoku-update" <<EOF
#!/usr/bin/env bash
exec bash "$DEST/update.sh"
EOF
chmod +x "$BIN/sudoku-update"
echo "Launchers: $BIN/sudoku, $BIN/sudoku-update"

# PATH hint if needed
case ":${PATH}:" in
    *":$BIN:"*) ;;
    *) echo "" && echo "NOTE: Add to your shell profile:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

echo ""
echo "Done. Run: sudoku"
