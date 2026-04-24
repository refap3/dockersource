#!/usr/bin/env bash
# ouroboros (watchtower) — installer
#
# From repo root:   bash ouroboros/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== ouroboros (watchtower) — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# This container is configured for on-demand use only (WATCHTOWER_RUN_ONCE=true,
# restart: "no"). Running dcud registers it but the container exits immediately
# after pulling updates. To trigger an update run later:
#
#   docker start watchtower && docker logs -f watchtower
#
# Old images are removed automatically (WATCHTOWER_CLEANUP=true).
echo "No configuration required."
echo "Note: container exits after each run — trigger manually with: docker start watchtower"

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting watchtower (run-once) ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Watchtower is running its first update pass — follow with: docker logs -f watchtower"
