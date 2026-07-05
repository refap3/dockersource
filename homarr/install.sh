#!/usr/bin/env bash
# homarr — installer
#
# From repo root:   bash homarr/install.sh
# From service dir: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== homarr — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Required: SECRET_ENCRYPTION_KEY in .env — a 64-character hex string used to
# encrypt stored credentials. Generate once and never change it; rotating the
# key will invalidate all saved integration secrets.

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

KEY="$(grep -E '^SECRET_ENCRYPTION_KEY=' .env | cut -d= -f2-)"
if [[ -z "$KEY" || "$KEY" == "your-64-char-hex-key-here" ]]; then
    if command -v openssl &>/dev/null; then
        GENERATED="$(openssl rand -hex 32)"
    else
        # Fallback: 32 random bytes as hex from /dev/urandom (no openssl needed)
        GENERATED="$(head -c 32 /dev/urandom | od -An -v -tx1 | tr -d ' \n')"
    fi
    if [[ ${#GENERATED} -ne 64 ]]; then
        echo "ERROR: failed to generate a 64-char hex key." >&2
        exit 1
    fi
    # Use a temp file to avoid sed -i portability issues
    TMP="$(mktemp)"
    grep -v '^SECRET_ENCRYPTION_KEY=' .env > "$TMP"
    echo "SECRET_ENCRYPTION_KEY=$GENERATED" >> "$TMP"
    mv "$TMP" .env
    echo ""
    echo ">>> SECRET_ENCRYPTION_KEY generated and written to .env."
fi

echo "SECRET_ENCRYPTION_KEY is set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting homarr ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

# ── Admin user ──────────────────────────────────────────────────────────────────
# Created directly in the DB so the web onboarding wizard never runs (a stale
# browser tab can silently skip its user step — see README). Interactive
# prompt, or set HOMARR_ADMIN_USER / HOMARR_ADMIN_PASSWORD for automation.
echo "Waiting for homarr to initialize ..."
DB_READY=0
for _ in $(seq 1 60); do
    if docker exec homarr node -e 'require("better-sqlite3")("/appdata/db/db.sqlite").prepare("SELECT count(*) AS c FROM user").get()' &>/dev/null; then
        DB_READY=1
        break
    fi
    sleep 2
done
if [[ "$DB_READY" -ne 1 ]]; then
    echo "ERROR: homarr did not initialize within 120s." >&2
    exit 1
fi

HAS_USERS="$(docker exec homarr node -e 'console.log(require("better-sqlite3")("/appdata/db/db.sqlite").prepare("SELECT count(*) AS c FROM user").get().c)')"
if [[ "$HAS_USERS" != "0" ]]; then
    echo "Admin user already exists — skipping."
else
    ADMIN_USER="${HOMARR_ADMIN_USER:-}"
    ADMIN_PASSWORD="${HOMARR_ADMIN_PASSWORD:-}"
    if [[ -z "$ADMIN_USER" || -z "$ADMIN_PASSWORD" ]]; then
        if [[ -t 0 ]]; then
            read -r -p "Admin username [admin]: " ADMIN_USER
            ADMIN_USER="${ADMIN_USER:-admin}"
            while :; do
                read -r -s -p "Admin password (min 8 chars): " ADMIN_PASSWORD; echo
                if [[ ${#ADMIN_PASSWORD} -lt 8 ]]; then echo "Too short, try again."; continue; fi
                read -r -s -p "Repeat password: " ADMIN_PASSWORD2; echo
                if [[ "$ADMIN_PASSWORD" == "$ADMIN_PASSWORD2" ]]; then break; fi
                echo "Passwords do not match, try again."
            done
        else
            echo ">>> No TTY and HOMARR_ADMIN_USER/HOMARR_ADMIN_PASSWORD not set."
            echo ">>> Skipping admin creation — rerun install.sh interactively to add one."
            ADMIN_USER=""
        fi
    fi
    if [[ -n "$ADMIN_USER" ]]; then
        docker exec -i -e ADMIN_USER="$ADMIN_USER" -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
            homarr node < "$SCRIPT_DIR/create-admin.js"
        docker restart homarr >/dev/null
        echo "Admin user ready — log in directly, no onboarding wizard needed."
    fi
fi

echo ""
echo "Done. Dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):7575"
