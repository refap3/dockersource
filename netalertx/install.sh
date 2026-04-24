#!/usr/bin/env bash
# netalertx — installer
#
# From repo root:   bash netalertx/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== netalertx — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# netalertx runs with host networking and NET_ADMIN + NET_RAW capabilities so
# it can scan the local network for connected devices. On first start, open
# the UI and configure:
#   - Scan range (CIDR) under Settings → Network
#   - Notification channels (email, Telegram, etc.) if desired
#
# PUID/PGID default to 20211. Adjust in docker-compose.yml if needed for
# file permission alignment on the host.
echo "No configuration required."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting netalertx ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. UI: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):20211"
