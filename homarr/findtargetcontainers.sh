#!/usr/bin/env bash
# findtargetcontainers.sh — sync local Docker containers onto the homarr dashboard.
#
# Scans the containers running on this node and mirrors them as app tiles on
# the default homarr board:
#   - newly found containers are added (name, URL from published port, icon)
#   - containers that no longer exist are removed again
#   - changed URLs/icons are updated
# Manually created tiles are never touched — the script only manages apps it
# created itself (tagged in the app description). Safe to re-run any time,
# e.g. from cron.
#
# Usage:
#   bash findtargetcontainers.sh [--dry-run] [--all] [--board <name>]
#                                [--container <homarr-container>] [--keep-defaults]
#                                [--keep-private]
#
#   --dry-run        show what would change, write nothing
#   --all            include stopped containers (default: running only)
#   --board NAME     sync onto this board (default: homarr's home board)
#   --container N    homarr container name (default: auto-detect by image)
#   --keep-defaults  keep the onboarding wizard's leftovers (sample links like
#                    Homarr Docs, docker-import tiles, default widgets);
#                    default: removed (widgets only once per install)
#   --keep-private   leave board visibility untouched; default: the target
#                    board is made public (viewable without login, editing
#                    still requires an account)
#
# Per-container overrides via docker labels:
#   homarr.ignore=true   never add this container
#   homarr.url=<url>     use this URL for the tile
#   homarr.icon=<url>    use this icon for the tile
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DRY_RUN=0
INCLUDE_STOPPED=0
KEEP_DEFAULTS=0
KEEP_PRIVATE=0
BOARD="${FTC_BOARD:-}"
HOMARR_CONTAINER="${FTC_CONTAINER:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --all) INCLUDE_STOPPED=1 ;;
        --keep-defaults) KEEP_DEFAULTS=1 ;;
        --keep-private) KEEP_PRIVATE=1 ;;
        --board) BOARD="$2"; shift ;;
        --container) HOMARR_CONTAINER="$2"; shift ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

echo "=== homarr — sync docker containers to dashboard ==="

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found." >&2
    exit 1
fi

# ── Locate the homarr container ────────────────────────────────────────────────
if [[ -z "$HOMARR_CONTAINER" ]]; then
    HOMARR_CONTAINER="$(docker ps --filter ancestor=ghcr.io/homarr-labs/homarr:latest --format '{{.Names}}' | head -1)"
fi
if [[ -z "$HOMARR_CONTAINER" ]] || ! docker ps --format '{{.Names}}' | grep -qx "$HOMARR_CONTAINER"; then
    echo "ERROR: running homarr container not found (try --container <name>)." >&2
    exit 1
fi
echo "homarr container: $HOMARR_CONTAINER"

# ── Host IP for the tile URLs ──────────────────────────────────────────────────
HOST_IP="${FTC_HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
if [[ -z "$HOST_IP" ]]; then
    echo "ERROR: could not determine host IP — set FTC_HOST_IP." >&2
    exit 1
fi
echo "host IP: $HOST_IP"

# ── Backup DB, then sync ───────────────────────────────────────────────────────
if [[ "$DRY_RUN" -eq 0 ]]; then
    docker exec "$HOMARR_CONTAINER" cp /appdata/db/db.sqlite /appdata/db/db.sqlite.ftc-backup
    echo "DB backup: /appdata/db/db.sqlite.ftc-backup (inside homarr_appdata volume)"
fi

docker exec -i \
    -e FTC_HOST_IP="$HOST_IP" \
    -e FTC_SELF="$HOMARR_CONTAINER" \
    -e FTC_BOARD="$BOARD" \
    -e FTC_DRY_RUN="$DRY_RUN" \
    -e FTC_INCLUDE_STOPPED="$INCLUDE_STOPPED" \
    -e FTC_KEEP_DEFAULTS="$KEEP_DEFAULTS" \
    -e FTC_KEEP_PRIVATE="$KEEP_PRIVATE" \
    "$HOMARR_CONTAINER" node < "$SCRIPT_DIR/sync-homarr-apps.js"

echo ""
echo "Done. Reload the homarr board in the browser to see the changes."
