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
# Twingate provides a pre-filled docker run command in the dashboard.
# We parse it to extract credentials rather than requiring manual .env editing.

extract_env() {
    local cmd="$1" key="$2"
    echo "$cmd" | grep -oE "\-e[[:space:]]+${key}=[^[:space:]]+" | sed "s/-e[[:space:]]*${key}=//" || true
}

if [[ ! -f .env ]] || \
   grep -qE '^TWINGATE_ACCESS_TOKEN=your-access-token$' .env 2>/dev/null; then

    echo ""
    echo "  How to get the command:"
    echo "    1. Go to https://app.twingate.com → your network → Connectors"
    echo "    2. Add or select a connector → click 'Generate Tokens'"
    echo "    3. Choose Docker → copy the 'docker run ...' command shown"
    echo "       (use the copy icon to get it as a single line)"
    echo ""
    read -r -p "Paste docker run command: " DOCKER_RUN_CMD

    NETWORK="$(extract_env "$DOCKER_RUN_CMD" TWINGATE_NETWORK)"
    ACCESS="$(extract_env "$DOCKER_RUN_CMD" TWINGATE_ACCESS_TOKEN)"
    REFRESH="$(extract_env "$DOCKER_RUN_CMD" TWINGATE_REFRESH_TOKEN)"

    if [[ -z "$NETWORK" || -z "$ACCESS" || -z "$REFRESH" ]]; then
        echo ""
        echo "DEBUG — received command:" >&2
        echo "$DOCKER_RUN_CMD" | sed 's/TOKEN=[^ ]*/TOKEN=REDACTED/g' >&2
        echo ""
        echo "ERROR: could not parse TWINGATE_NETWORK, TWINGATE_ACCESS_TOKEN, and" >&2
        echo "       TWINGATE_REFRESH_TOKEN from that command." >&2
        exit 1
    fi

    cat > .env <<EOF
TWINGATE_NETWORK=$NETWORK
TWINGATE_ACCESS_TOKEN=$ACCESS
TWINGATE_REFRESH_TOKEN=$REFRESH
TWINGATE_LABEL_HOSTNAME=$(hostname -s)
EOF
    echo ""
    echo ">>> .env written with credentials for network: $NETWORK"
fi

echo "Credentials are set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting twingate-connector ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Connector should appear as online in your Twingate dashboard."
