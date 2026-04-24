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
# Required: TUNNEL_TOKEN in .env
#   1. Log in to Cloudflare Zero Trust dashboard (one.dash.cloudflare.com)
#   2. Go to Networks → Tunnels → Create a tunnel
#   3. Copy the tunnel token and paste it into .env

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

TUNNEL_TOKEN="$(grep -E '^TUNNEL_TOKEN=' .env | cut -d= -f2-)"
if [[ -z "$TUNNEL_TOKEN" || "$TUNNEL_TOKEN" == "your-cloudflare-tunnel-token-here" ]]; then
    echo ""
    echo "ACTION REQUIRED — set TUNNEL_TOKEN in .env before starting:"
    echo "  1. Open Cloudflare Zero Trust: https://one.dash.cloudflare.com"
    echo "  2. Networks → Tunnels → Create a tunnel → copy the token"
    echo "  3. Edit .env and replace the placeholder:"
    echo "     TUNNEL_TOKEN=<your-token>"
    echo ""
    echo "Then re-run this script."
    exit 0
fi

echo "TUNNEL_TOKEN is set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting cloudflared ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Tunnel is connecting — check status in the Cloudflare dashboard."
