#!/usr/bin/env bash
# wallabag — installer
#
# From repo root:   bash wallabag/install.sh
# From service dir: bash install.sh
#
# Starts the container (SQLite backend, no extra DB container), then:
#   - generates SYMFONY__ENV__SECRET and the public URL into .env
#   - changes the password of the built-in "wallabag" admin user
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== wallabag — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"
[[ -n "$IP" ]] || IP=localhost

# ── Configuration ──────────────────────────────────────────────────────────────
# Required in .env:
#   WALLABAG_SECRET      — Symfony secret, must stay stable after first start
#   WALLABAG_DOMAIN_NAME — URL the browser/apps use; wrong value breaks share
#                          links and the API
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

SECRET="$(grep -E '^WALLABAG_SECRET=' .env | cut -d= -f2-)"
if [[ -z "$SECRET" || "$SECRET" == "your-64-char-hex-secret-here" ]]; then
    if command -v openssl &>/dev/null; then
        SECRET="$(openssl rand -hex 32)"
    else
        # Fallback: 32 random bytes as hex from /dev/urandom (no openssl needed)
        SECRET="$(head -c 32 /dev/urandom | od -An -v -tx1 | tr -d ' \n')"
    fi
    if [[ ${#SECRET} -ne 64 ]]; then
        echo "ERROR: failed to generate a 64-char hex secret." >&2
        exit 1
    fi
    # Use a temp file to avoid sed -i portability issues
    TMP="$(mktemp)"
    grep -v '^WALLABAG_SECRET=' .env > "$TMP"
    echo "WALLABAG_SECRET=$SECRET" >> "$TMP"
    mv "$TMP" .env
    echo ">>> WALLABAG_SECRET generated and written to .env."
fi

DOMAIN="$(grep -E '^WALLABAG_DOMAIN_NAME=' .env | cut -d= -f2-)"
if [[ -z "$DOMAIN" || "$DOMAIN" == "http://your-host-ip:8085" ]]; then
    DOMAIN="${WALLABAG_DOMAIN_NAME:-http://$IP:8085}"
    TMP="$(mktemp)"
    grep -v '^WALLABAG_DOMAIN_NAME=' .env > "$TMP"
    echo "WALLABAG_DOMAIN_NAME=$DOMAIN" >> "$TMP"
    mv "$TMP" .env
    echo ">>> WALLABAG_DOMAIN_NAME set to $DOMAIN."
fi

echo "WALLABAG_SECRET and WALLABAG_DOMAIN_NAME are set."

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting wallabag ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

# ── Wait for first-run database setup ──────────────────────────────────────────
# The entrypoint creates the SQLite schema and the default user (wallabag/wallabag)
# on first start; that takes a while on a Pi.
echo "Waiting for wallabag to initialize (first start can take a few minutes) ..."
READY=0
for _ in $(seq 1 150); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8085/login" || true)"
    if [[ "$code" == "200" ]]; then
        READY=1
        break
    fi
    sleep 2
done
if [[ "$READY" -ne 1 ]]; then
    echo "ERROR: wallabag did not become ready. Check: docker logs wallabag" >&2
    exit 1
fi

# ── Admin password ─────────────────────────────────────────────────────────────
# The image always ships the default account wallabag/wallabag. Change it here,
# interactively or via WALLABAG_ADMIN_PASSWORD for automation.
console() {
    docker exec -u nobody wallabag /var/www/wallabag/bin/console "$@" --env=prod 2>/dev/null \
        || docker exec wallabag /var/www/wallabag/bin/console "$@" --env=prod
}

ADMIN_PASSWORD="${WALLABAG_ADMIN_PASSWORD:-}"
if [[ -z "$ADMIN_PASSWORD" ]]; then
    if [[ -t 0 ]]; then
        while :; do
            read -r -s -p "New password for user 'wallabag' (min 8 chars): " ADMIN_PASSWORD; echo
            if [[ ${#ADMIN_PASSWORD} -lt 8 ]]; then echo "Too short, try again."; continue; fi
            read -r -s -p "Repeat password: " ADMIN_PASSWORD2; echo
            if [[ "$ADMIN_PASSWORD" == "$ADMIN_PASSWORD2" ]]; then break; fi
            echo "Passwords do not match, try again."
        done
    else
        echo ">>> No TTY and WALLABAG_ADMIN_PASSWORD not set."
        echo ">>> Default login stays wallabag / wallabag — change it after first login."
    fi
fi

if [[ -n "$ADMIN_PASSWORD" ]]; then
    if console fos:user:change-password wallabag "$ADMIN_PASSWORD" >/dev/null; then
        echo "Password for user 'wallabag' updated."
    else
        echo "WARNING: could not change the password automatically." >&2
        echo "         Log in with wallabag / wallabag and change it in the UI." >&2
    fi
fi

# ── Verify ─────────────────────────────────────────────────────────────────────
code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8085/login" || true)"
echo ""
echo "Done. UI: http://$IP:8085   [http $code]"
echo "  Login user: wallabag"
echo "  Public sign-up is disabled; add more users under Settings → Users (admin only)."
echo "  Browser extensions / mobile apps: server URL $DOMAIN"
