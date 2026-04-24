#!/usr/bin/env bash
# busybox — installer
#
# From repo root:   bash busybox/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== busybox — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# Note: this container mounts the full host filesystem at /host in privileged
# mode. It is a utility shell — not a long-running service. Use:
#   docker exec -it busybox sh
echo "No configuration required."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting busybox ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Run 'docker exec -it busybox sh' to open a shell."
