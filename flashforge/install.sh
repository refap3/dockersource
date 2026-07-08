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
#
# Also asks for a camera stream URL (default http://192.168.1.37:9081/,
# CAMERA_URL for non-interactive use) — ideally the MJPEG stream of a camera
# that is also integrated in Home Assistant (e.g. a motionEye camera's
# streaming port). The upstream templates are patched to embed that stream
# in the GUI's video section (must be MJPEG or a plain image URL — an <img>
# tag, no RTSP/HLS). Enter "-" to use the printer's own camera instead
# (http://<printer-ip>:8080/?action=stream — 5M Pro / camera accessory only).
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

# ── Configuration: camera stream URL ───────────────────────────────────────────
# Default: CAMERA_URL env var > existing .env value > http://192.168.1.37:9081/
DEFAULT_CAMERA_URL="http://192.168.1.37:9081/"
if [[ -z "${CAMERA_URL:-}" ]] && [[ -f .env ]] && grep -q '^CAMERA_URL=' .env; then
    CAMERA_URL="$(sed -n 's/^CAMERA_URL=//p' .env | head -1)"
else
    CAMERA_URL="${CAMERA_URL:-$DEFAULT_CAMERA_URL}"
fi

if [[ -t 0 ]]; then
    echo "Camera for the GUI's video section — ideally the MJPEG stream of a camera"
    echo "that is also integrated in Home Assistant (e.g. a motionEye streaming port)."
    read -r -p "Camera stream URL ('-' = use printer's own camera) [${CAMERA_URL:-printer camera}]: " answer
    if [[ "$answer" == "-" ]]; then
        CAMERA_URL=""
    elif [[ -n "$answer" ]]; then
        CAMERA_URL="$answer"
    fi
else
    echo "No TTY — using camera URL '${CAMERA_URL:-<printer camera>}' (override with CAMERA_URL=...)."
fi
# CAMERA_URL=- also works non-interactively to select the printer's own camera
[[ "$CAMERA_URL" == "-" ]] && CAMERA_URL=""

if [[ -n "$CAMERA_URL" ]] && ! printf '%s' "$CAMERA_URL" | grep -Eq '^https?://'; then
    echo "ERROR: camera URL '$CAMERA_URL' must start with http:// or https://." >&2
    exit 1
fi

{
    echo "PRINTER_IP=$PRINTER_IP"
    echo "CAMERA_URL=$CAMERA_URL"
} > .env
echo "Printer IP: $PRINTER_IP (saved to .env)"
echo "Camera URL: ${CAMERA_URL:-<printer camera>} (saved to .env)"

# ── Fetch upstream source ──────────────────────────────────────────────────────
# The Dockerfile copies ./adventurer5m into the image; the source lives in the
# upstream repo, so (re-)clone it fresh on every install to pick up updates.
echo "Fetching upstream source ..."
rm -rf adventurer5m
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 "$UPSTREAM" "$TMP/repo"
cp -r "$TMP/repo/adventurer5m" ./adventurer5m

# ── Patch camera feed (optional) ────────────────────────────────────────────────
# Upstream templates hardcode the printer's own camera:
#   <img id="video_feed" src="http://{{ printer_ip }}:8080/?action=stream" ...>
# Replace that src with CAMERA_URL if one was configured.
if [[ -n "$CAMERA_URL" ]]; then
    echo "Patching camera feed to $CAMERA_URL ..."
    ESCAPED_URL="$(printf '%s' "$CAMERA_URL" | sed 's/[&|\\]/\\&/g')"
    patched=0
    for tpl in adventurer5m/templates/index_*.html; do
        [[ -f "$tpl" ]] || continue
        if grep -q 'id="video_feed"' "$tpl"; then
            sed -i.bak "s|src=\"http://{{ printer_ip }}:8080/?action=stream\"|src=\"$ESCAPED_URL\"|" "$tpl"
            rm -f "$tpl.bak"
            grep -q "$CAMERA_URL" "$tpl" && patched=$((patched + 1))
        fi
    done
    if [[ "$patched" -eq 0 ]]; then
        echo "WARNING: no template patched — upstream markup may have changed; GUI keeps the printer camera." >&2
    else
        echo "Camera feed patched in $patched template(s)."
    fi
fi

# ── Build & start ──────────────────────────────────────────────────────────────
echo "Building and starting FlashForgeAdventurer5MAPI ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d --build; }
dcud

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"
echo ""
echo "Done. GUI: http://$HOST_IP:9876/en/$PRINTER_IP"
echo "API example: curl http://$HOST_IP:9876/api/execute/$PRINTER_IP/progress"
