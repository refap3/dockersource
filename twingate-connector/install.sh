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
if [[ ! -f .env ]] || \
   grep -qE '^TWINGATE_ACCESS_TOKEN=your-access-token$' .env 2>/dev/null; then

    echo ""
    echo "Get these values from: https://app.twingate.com → your network → Connectors"
    echo "Add or select a connector → Generate Tokens → choose Docker."
    echo ""
    read -r -p "Network name (e.g. mycompany, without .twingate.com): " NETWORK
    read -r -p "Access token:  " ACCESS
    read -r -p "Refresh token: " REFRESH

    if [[ -z "$NETWORK" || -z "$ACCESS" || -z "$REFRESH" ]]; then
        echo "ERROR: all three values are required." >&2
        exit 1
    fi

    cat > .env <<EOF
TWINGATE_NETWORK=$NETWORK
TWINGATE_ACCESS_TOKEN=$ACCESS
TWINGATE_REFRESH_TOKEN=$REFRESH
TWINGATE_LABEL_HOSTNAME=$(hostname -s)
EOF
    echo ""
    echo ">>> .env written for network: $NETWORK"
fi

echo "Credentials are set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting twingate-connector ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Connector should appear as online in your Twingate dashboard."
