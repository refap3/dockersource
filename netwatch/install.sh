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
    git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/repo" -q
    git -C "$TMP/repo" sparse-checkout set "$SUBDIR" -q
    mkdir -p "$DEST"
    cp -r "$TMP/repo/$SUBDIR/." "$DEST/"
fi

echo "=== netwatch — install ==="
cd "$DEST"

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

if [[ ! -f config.yml ]]; then
    cp config.yml.example config.yml
    echo ""
    echo ">>> config.yml created from example."
    echo ">>> Edit it now to set your network CIDR and interface, then re-run this script."
    echo "    nano $DEST/config.yml"
    echo ""
    exit 0
fi

echo "Building and starting netwatch ..."
docker compose up -d --build

echo ""
echo "Done. Dashboard: http://$(hostname -I | awk '{print $1}'):8095"
