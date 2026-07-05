#!/usr/bin/env bash
# marcujump — installer
#
# From repo root:   bash marcujump/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== marcujump — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# No configuration required.
#
# The game ("Markus im Weltall") is fetched from GitHub at build time, so the
# image always contains the current version of the upstream repo. Run
# update.sh later to rebuild only when the upstream index.html has changed.
echo "No configuration required."

# ── Build & start ──────────────────────────────────────────────────────────────
REPO_URL="https://github.com/refap3/marcujump.git"
REMOTE_SHA="$(git ls-remote "$REPO_URL" HEAD 2>/dev/null | cut -f1 || true)"
[ -n "$REMOTE_SHA" ] || REMOTE_SHA="unknown"

echo "Building marcujump (upstream commit: $REMOTE_SHA) ..."
docker compose build --build-arg MARCUJUMP_SHA="$REMOTE_SHA"

echo "Starting marcujump ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done. Game: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8093"
echo "Guide: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8093/MarcuJumpGuide.html"
