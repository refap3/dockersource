#!/usr/bin/env bash
# cloudflared — installer
#
# From repo root:   bash cloudflared/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== cloudflared — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
if [[ ! -f .env ]] || \
   grep -qE '^TUNNEL_TOKEN=your-cloudflare-tunnel-token-here$' .env 2>/dev/null; then

    # Remove any leftover container that would cause a name conflict with docker run
    docker rm -f cloudflared 2>/dev/null || true

    echo ""
    echo "  1. Get the docker run command from the Cloudflare dashboard:"
    echo "     https://one.dash.cloudflare.com → Networks → Tunnels → your tunnel → Configure"
    echo "     (or create a new tunnel and select Docker as the environment)"
    echo ""
    echo "  2. Open a second SSH session to this machine and run that command."
    echo "     (new terminal tab → rap $(hostname -I | awk '{print $1}' | awk -F. '{print $NF}'))"
    echo ""
    read -r -p "Press Enter once the container is running: "

    # Find the container by image — token is a command arg, not an env var
    TEMP="$(docker ps --format '{{.Names}} {{.Image}}' | awk '/cloudflare\/cloudflared/{print $1}' | head -1 || true)"

    if [[ -z "$TEMP" ]]; then
        echo "ERROR: no running cloudflare/cloudflared container found." >&2
        echo "       Start the container first, then re-run this script." >&2
        exit 1
    fi

    echo "Found container: $TEMP — extracting token ..."
    CMD="$(docker inspect "$TEMP" --format '{{join .Config.Cmd " "}}')"
    TUNNEL_TOKEN="$(echo "$CMD" | grep -oE '\-\-token [^ ]+' | awk '{print $2}' || true)"

    if [[ -z "$TUNNEL_TOKEN" ]]; then
        echo "ERROR: could not extract --token from container '$TEMP'." >&2
        exit 1
    fi

    echo "Stopping temporary container ..."
    docker stop "$TEMP" >/dev/null && docker rm "$TEMP" >/dev/null

    cat > .env <<EOF
TUNNEL_TOKEN=$TUNNEL_TOKEN
EOF
    echo ""
    echo ">>> .env written with tunnel token."
fi

echo "TUNNEL_TOKEN is set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting cloudflared ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Tunnel is connecting — check status in the Cloudflare dashboard."
