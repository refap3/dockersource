#!/usr/bin/env bash
# wg-easy — installer
#
# From repo root:   bash wg-easy/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== wg-easy — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration file required. All settings are in docker-compose.yml.
#
# The WireGuard kernel module must be available on the host:
#   - Linux / Raspberry Pi: included in kernel 5.6+; verify with: modinfo wireguard
#   - Synology NAS:         verify with: modinfo wireguard (not available on all models)
#   - macOS:                not supported natively; use a Linux VM or host
#
# If you need to expose WireGuard over a non-standard public IP/hostname,
# set the WG_HOST environment variable in docker-compose.yml before starting.
#
# Ports used:
#   51820/UDP — WireGuard tunnel traffic
#   51821/TCP — wg-easy web UI

echo "No configuration required."
if modinfo wireguard &>/dev/null 2>&1; then
    echo "WireGuard kernel module: available."
else
    echo "WARNING: 'modinfo wireguard' failed — the WireGuard kernel module may not be"
    echo "         loaded. The container will fail to start without it."
    echo "         On Synology, check DSM Package Center for WireGuard support."
fi

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting wg-easy ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. UI: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):51821"
