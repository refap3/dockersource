#!/usr/bin/env bash
# sudokusolver — Docker installer
#
# From repo root:   bash sudokusolver/install.sh
# From service dir: bash install.sh
#
# For the standalone desktop app (Mac/Linux), see:
#   https://github.com/refap3/claudeCode/blob/main/sudokusolver/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== sudokusolver — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Optional: ANTHROPIC_API_KEY in .env
#   Required only for the image/screenshot import feature (Claude vision).
#   The solver works fully without it — manual puzzle entry and all 30 built-in
#   puzzles are available regardless.
#
#   To enable image import:
#     1. Get an API key from https://console.anthropic.com
#     2. Set ANTHROPIC_API_KEY=sk-ant-... in .env

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

KEY="$(grep -E '^ANTHROPIC_API_KEY=' .env | cut -d= -f2-)"
if [[ -z "$KEY" || "$KEY" == "sk-ant-..." ]]; then
    echo ""
    echo "INFO: ANTHROPIC_API_KEY is not set — image import will be disabled."
    echo "      Set it in .env to enable puzzle import from screenshots."
else
    echo "ANTHROPIC_API_KEY is set — image import enabled."
fi

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Building and starting sudokusolver ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d --build; }
dcud

echo ""
echo "Done. UI: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8011"
