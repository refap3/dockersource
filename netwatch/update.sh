#!/usr/bin/env bash
# netwatch — update script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="https://github.com/refap3/dockersource"
SUBDIR="netwatch"

echo "=== netwatch — update ==="

REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$REPO_ROOT" ]]; then
    echo "Pulling latest code ..."
    git -C "$REPO_ROOT" pull
else
    echo "Downloading latest files from GitHub ..."
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/repo"
    git -C "$TMP/repo" sparse-checkout set "$SUBDIR"
    # Preserve user's config.yml, overwrite everything else
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --exclude='config.yml' "$TMP/repo/$SUBDIR/" "$SCRIPT_DIR/"
    else
        [ -f "$SCRIPT_DIR/config.yml" ] && cp "$SCRIPT_DIR/config.yml" "$TMP/config.yml.bak"
        cp -r "$TMP/repo/$SUBDIR/." "$SCRIPT_DIR/"
        [ -f "$TMP/config.yml.bak" ] && cp "$TMP/config.yml.bak" "$SCRIPT_DIR/config.yml"
    fi
fi

cd "$SCRIPT_DIR"

if [[ ! -f config.yml ]]; then
    cp config.yml.example config.yml
    echo ""
    echo ">>> config.yml was missing — created from example."
    echo ">>> Edit it to set your network CIDR and interface, then re-run update.sh."
    echo "    nano $SCRIPT_DIR/config.yml"
    echo ""
    exit 0
fi

echo "Rebuilding container ..."
docker compose up -d --build

echo "Update complete."
