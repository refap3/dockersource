#!/usr/bin/env bash
# homarr — installer
#
# From repo root:   bash homarr/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== homarr — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Required: SECRET_ENCRYPTION_KEY in .env — a 64-character hex string used to
# encrypt stored credentials. Generate once and never change it; rotating the
# key will invalidate all saved integration secrets.

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

KEY="$(grep -E '^SECRET_ENCRYPTION_KEY=' .env | cut -d= -f2-)"
if [[ -z "$KEY" || "$KEY" == "your-64-char-hex-key-here" ]]; then
    if command -v openssl &>/dev/null; then
        GENERATED="$(openssl rand -hex 32)"
        # Use a temp file to avoid sed -i portability issues
        TMP="$(mktemp)"
        grep -v '^SECRET_ENCRYPTION_KEY=' .env > "$TMP"
        echo "SECRET_ENCRYPTION_KEY=$GENERATED" >> "$TMP"
        mv "$TMP" .env
        echo ""
        echo ">>> SECRET_ENCRYPTION_KEY generated and written to .env."
    else
        echo ""
        echo "ACTION REQUIRED — set SECRET_ENCRYPTION_KEY in .env before starting:"
        echo "  Generate: openssl rand -hex 32"
        echo "  Then set: SECRET_ENCRYPTION_KEY=<result> in .env"
        echo ""
        echo "Then re-run this script."
        exit 0
    fi
fi

echo "SECRET_ENCRYPTION_KEY is set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting homarr ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):7575"
