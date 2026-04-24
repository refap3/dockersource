#!/usr/bin/env bash
# portainer — installer
#
# From repo root:   bash portainer/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== portainer — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# On first start, Portainer presents a setup wizard to create the admin
# account. Complete it within 5 minutes — the setup page times out for
# security reasons.
echo "No configuration required."
echo "Note: complete the admin account setup in the UI within 5 minutes of first start."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting portainer ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. UI (HTTPS): https://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):9443"
echo "     UI (HTTP):  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):9000"
