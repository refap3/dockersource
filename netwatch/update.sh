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
    git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/repo" -q
    git -C "$TMP/repo" sparse-checkout set "$SUBDIR" -q
    # Preserve user's config.yml
    cp -r "$TMP/repo/$SUBDIR/." "$SCRIPT_DIR/" --no-clobber 2>/dev/null || \
        rsync -a --exclude='config.yml' "$TMP/repo/$SUBDIR/" "$SCRIPT_DIR/" 2>/dev/null || \
        cp -r "$TMP/repo/$SUBDIR/." "$SCRIPT_DIR/"
fi

cd "$SCRIPT_DIR"
echo "Rebuilding container ..."
docker compose up -d --build

echo "Update complete."
