#!/usr/bin/env bash
# netwatch — installer
#
# Fresh install (one line, no repo needed):
#   curl -fsSL https://raw.githubusercontent.com/refap3/dockersource/main/netwatch/install.sh | bash
#
# Already have the repo:
#   bash netwatch/install.sh      # from repo root
#   bash install.sh               # from netwatch/
set -euo pipefail

REPO="https://github.com/refap3/dockersource"
SUBDIR="netwatch"

# ── Detect local vs fresh (curl) mode ─────────────────────────────────────────
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" != "bash" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
fi

if [[ -n "$SCRIPT_DIR" ]] && [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    DEST="$SCRIPT_DIR"
else
    DEST="${NETWATCH_DIR:-$HOME/netwatch}"
    echo "Cloning netwatch from GitHub ..."
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/repo"
    git -C "$TMP/repo" sparse-checkout set "$SUBDIR"
    mkdir -p "$DEST"
    cp -r "$TMP/repo/$SUBDIR/." "$DEST/"
fi

echo "=== netwatch — install ==="
cd "$DEST"

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Required: config.yml — must exist before the container starts. If Docker
# runs first without it, Docker creates config.yml as a directory and the
# container fails permanently until manually removed.
#
# Key settings to configure in config.yml:
#   scanner.network   — CIDR range to scan, e.g. 192.168.1.0/24
#   scanner.interface — network interface, e.g. eth0 or wlan0
#
# Optional: webhook, Telegram, or SMTP notification settings.

if [[ ! -f config.yml ]]; then
    cp config.yml.example config.yml
    echo ""
    echo ">>> config.yml created from config.yml.example."
    echo ">>> Edit it now to set your network CIDR and interface, then re-run this script."
    echo "    nano $DEST/config.yml"
    echo ""
    exit 0
fi

echo "config.yml is present."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Building and starting netwatch ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d --build; }
dcud

echo ""
echo "Done. Dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8095"
