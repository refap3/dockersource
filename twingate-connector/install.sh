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

    # Remove any leftover container that would cause a name conflict with docker run
    docker rm -f twingate-connector 2>/dev/null || true

    echo ""
    echo "  1. Get the docker run command from the Twingate dashboard:"
    echo "     https://app.twingate.com → your network → Connectors → Generate Tokens → Docker"
    echo ""
    echo "  2. Open a second SSH session to this machine and run that command."
    echo "     (new terminal tab → rap $(hostname -I | awk '{print $1}' | awk -F. '{print $NF}'))"
    echo ""
    read -r -p "Press Enter once the container is running: "

    # Find the container by image — works regardless of what name docker run used
    TEMP="$(docker ps --format '{{.Names}} {{.Image}}' | awk '/twingate\/connector/{print $1}' | head -1 || true)"

    if [[ -z "$TEMP" ]]; then
        echo "ERROR: no running twingate/connector container found." >&2
        echo "       Start the container first, then re-run this script." >&2
        exit 1
    fi

    echo "Found container: $TEMP — extracting credentials ..."
    ENVS="$(docker inspect "$TEMP" --format '{{range .Config.Env}}{{println .}}{{end}}')"
    NETWORK="$(echo "$ENVS" | grep '^TWINGATE_NETWORK='     | cut -d= -f2-)"
    ACCESS="$(echo  "$ENVS" | grep '^TWINGATE_ACCESS_TOKEN=' | cut -d= -f2-)"
    REFRESH="$(echo "$ENVS" | grep '^TWINGATE_REFRESH_TOKEN='| cut -d= -f2-)"

    if [[ -z "$NETWORK" || -z "$ACCESS" || -z "$REFRESH" ]]; then
        echo "ERROR: could not extract credentials from container '$TEMP'." >&2
        exit 1
    fi

    echo "Stopping temporary container ..."
    docker stop "$TEMP" >/dev/null && docker rm "$TEMP" >/dev/null

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
