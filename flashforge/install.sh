#!/usr/bin/env bash
# flashforge — installer
#
# Web API + GUI for a FlashForge Adventurer 5M (Pro) printer, from
# https://github.com/IgorZyktin/FlashForgeAdventurer5MAPI
#
# From repo root:   bash flashforge/install.sh
# From service dir: bash install.sh
#
# Asks for the printer IP (default 192.168.1.113); non-interactive installs
# can set PRINTER_IP instead. The IP is stored in .env and attached to the
# container as the label flashforge.printer_ip, which homarr's
# findtargetcontainers.sh uses to build the tile URL
# http://<docker-host>:9876/en/<printer-ip>.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

UPSTREAM="https://github.com/IgorZyktin/FlashForgeAdventurer5MAPI.git"

echo "=== flashforge — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi
if ! command -v git &>/dev/null; then
    echo "ERROR: git not found. Install git and try again." >&2
    exit 1
fi

# ── Configuration: printer IP ──────────────────────────────────────────────────
# Default: PRINTER_IP env var > existing .env value > 192.168.1.113
DEFAULT_IP="192.168.1.113"
if [[ -z "${PRINTER_IP:-}" ]] && [[ -f .env ]]; then
    PRINTER_IP="$(sed -n 's/^PRINTER_IP=//p' .env | head -1)"
fi
PRINTER_IP="${PRINTER_IP:-$DEFAULT_IP}"

if [[ -t 0 ]]; then
    read -r -p "FlashForge printer IP [$PRINTER_IP]: " answer
    [[ -n "$answer" ]] && PRINTER_IP="$answer"
else
    echo "No TTY — using printer IP $PRINTER_IP (override with PRINTER_IP=...)."
fi

if ! printf '%s' "$PRINTER_IP" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'; then
    echo "ERROR: '$PRINTER_IP' is not a valid IPv4 address." >&2
    exit 1
fi

echo "PRINTER_IP=$PRINTER_IP" > .env
echo "Printer IP: $PRINTER_IP (saved to .env)"

# ── Fetch upstream source ──────────────────────────────────────────────────────
# The Dockerfile copies ./adventurer5m into the image; the source lives in the
# upstream repo, so (re-)clone it fresh on every install to pick up updates.
echo "Fetching upstream source ..."
rm -rf adventurer5m
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 "$UPSTREAM" "$TMP/repo"
cp -r "$TMP/repo/adventurer5m" ./adventurer5m

# ── Build & start ──────────────────────────────────────────────────────────────
echo "Building and starting FlashForgeAdventurer5MAPI ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d --build; }
dcud

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"
echo ""
echo "Done. GUI: http://$HOST_IP:9876/en/$PRINTER_IP"
echo "API example: curl http://$HOST_IP:9876/api/execute/$PRINTER_IP/progress"
