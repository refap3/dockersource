#!/usr/bin/env bash
# marcujump — updater
#
# Compares the upstream index.html (GitHub HEAD) with the copy inside the
# running container and rebuilds + restarts only if the game has changed.
#
# From repo root:   bash marcujump/update.sh
# From service dir: bash update.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REPO_URL="https://github.com/refap3/marcujump.git"
RAW_INDEX="https://raw.githubusercontent.com/refap3/marcujump/main/index.html"
CONTAINER="marcujump"

echo "=== marcujump — update check ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found." >&2
    exit 1
fi

# Portable SHA-256 (sha256sum on Linux, shasum on macOS)
hash_stdin() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum | cut -d' ' -f1
    else
        shasum -a 256 | cut -d' ' -f1
    fi
}

fetch_remote_index() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$RAW_INDEX"
    else
        wget -qO- "$RAW_INDEX"
    fi
}

rebuild() {
    REMOTE_SHA="$(git ls-remote "$REPO_URL" HEAD 2>/dev/null | cut -f1 || true)"
    [ -n "$REMOTE_SHA" ] || REMOTE_SHA="unknown"
    echo "Rebuilding marcujump (upstream commit: $REMOTE_SHA) ..."
    docker compose build --no-cache --pull --build-arg MARCUJUMP_SHA="$REMOTE_SHA"
    docker compose up -d
    echo "Update complete."
}

# ── Not running yet? Just build and start. ─────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "Container '$CONTAINER' not running — building and starting."
    rebuild
    exit 0
fi

# ── Compare upstream index.html with the one inside the container ──────────────
REMOTE_HASH="$(fetch_remote_index | hash_stdin)"
LOCAL_HASH="$(docker exec "$CONTAINER" cat /usr/share/nginx/html/index.html | hash_stdin)"

if [ -z "$REMOTE_HASH" ]; then
    echo "ERROR: could not fetch upstream index.html from $RAW_INDEX" >&2
    exit 1
fi

if [ "$REMOTE_HASH" = "$LOCAL_HASH" ]; then
    echo "index.html unchanged upstream — nothing to do."
    exit 0
fi

echo "Upstream index.html has changed — updating."
rebuild
