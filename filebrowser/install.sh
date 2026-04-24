#!/usr/bin/env bash
# filebrowser — installer
#
# From repo root:   bash filebrowser/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== filebrowser — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# A random admin password is generated on first start. Retrieve it with:
#   docker logs filebrowser
#
# The entire host filesystem is mounted at /srv (read-write). Change the
# admin password after first login via Settings → User Management.
echo "No configuration required."
echo "Note: retrieve the generated admin password after start with: docker logs filebrowser"

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting filebrowser ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. UI: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8099"
echo "Run 'docker logs filebrowser' to retrieve the generated admin password."
