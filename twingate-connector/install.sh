#!/usr/bin/env bash
# twingate-connector — installer
#
# From repo root:   bash twingate-connector/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== twingate-connector — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Required: three credentials in .env, all obtained from the Twingate admin
# dashboard (app.twingate.com) under your network's Connectors section:
#
#   TWINGATE_NETWORK       — e.g. yournetwork.twingate.com
#   TWINGATE_ACCESS_TOKEN  — connector access token
#   TWINGATE_REFRESH_TOKEN — connector refresh token
#
# Optional:
#   TWINGATE_LABEL_HOSTNAME — friendly name shown in the dashboard
#                             (defaults to the container's auto-generated ID)

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

MISSING=()
NETWORK="$(grep -E '^TWINGATE_NETWORK=' .env | cut -d= -f2-)"
ACCESS="$(grep -E '^TWINGATE_ACCESS_TOKEN=' .env | cut -d= -f2-)"
REFRESH="$(grep -E '^TWINGATE_REFRESH_TOKEN=' .env | cut -d= -f2-)"

[[ -z "$NETWORK"  || "$NETWORK"  == "yournetwork.twingate.com" ]] && MISSING+=(TWINGATE_NETWORK)
[[ -z "$ACCESS"   || "$ACCESS"   == "your-access-token"        ]] && MISSING+=(TWINGATE_ACCESS_TOKEN)
[[ -z "$REFRESH"  || "$REFRESH"  == "your-refresh-token"       ]] && MISSING+=(TWINGATE_REFRESH_TOKEN)

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo ""
    echo "ACTION REQUIRED — set the following variables in .env before starting:"
    for var in "${MISSING[@]}"; do
        echo "  $var"
    done
    echo ""
    echo "Get these values from: https://app.twingate.com → your network → Connectors"
    echo ""
    echo "Then re-run this script."
    exit 0
fi

echo "All required credentials are set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting twingate-connector ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Connector should appear as online in your Twingate dashboard."
