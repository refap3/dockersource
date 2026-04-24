#!/usr/bin/env bash
# dozzle — installer
#
# From repo root:   bash dozzle/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== dozzle — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# Dozzle mounts the Docker socket (read-only) to stream container logs in
# real time. Actions (restart/stop) and shell access are enabled via
# DOZZLE_ENABLE_ACTIONS and DOZZLE_ENABLE_SHELL in docker-compose.yml.
echo "No configuration required."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting dozzle ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8077"
