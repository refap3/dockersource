#!/usr/bin/env bash
# calibre — installer
#
# From repo root:   bash calibre/install.sh
# From service dir: bash install.sh
#
# Starts the container, then bootstraps it for immediate use:
#   - creates the library at /config/Calibre Library
#   - skips the welcome wizard
#   - enables the content server on port 8081 (auto-starts with calibre)
#   - creates a content-server user with upload (write) permission
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== calibre — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Content-server credentials are generated once and stored in .env (gitignored).
if [ -f .env ]; then
    # shellcheck disable=SC1091
    . ./.env
fi
CALIBRE_UPLOAD_USER="${CALIBRE_UPLOAD_USER:-calibre}"
if [ -z "${CALIBRE_UPLOAD_PASSWORD:-}" ]; then
    CALIBRE_UPLOAD_PASSWORD="$(openssl rand -hex 8)"
    {
        echo "CALIBRE_UPLOAD_USER=$CALIBRE_UPLOAD_USER"
        echo "CALIBRE_UPLOAD_PASSWORD=$CALIBRE_UPLOAD_PASSWORD"
    } > .env
    echo "Generated content-server credentials (saved to .env)."
fi

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting calibre ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo "Waiting for container to come up ..."
ready=0
for _ in $(seq 1 60); do
    if docker exec calibre test -d /config 2>/dev/null; then
        ready=1
        break
    fi
    sleep 2
done
if [ "$ready" -ne 1 ]; then
    echo "ERROR: container did not become ready. Check: docker logs calibre" >&2
    exit 1
fi
sleep 5

# ── Bootstrap (idempotent) ─────────────────────────────────────────────────────
echo "Bootstrapping library and content server ..."
docker exec -u abc -e HOME=/config \
    -e BOOTSTRAP_USER="$CALIBRE_UPLOAD_USER" \
    -e BOOTSTRAP_PW="$CALIBRE_UPLOAD_PASSWORD" \
    calibre calibre-debug -c "
import os
lib = '/config/Calibre Library'
os.makedirs(lib, exist_ok=True)

# Create the library database if it does not exist yet
from calibre.library import db
db(lib)

# Point calibre at the library and skip the welcome wizard
from calibre.utils.config import prefs, dynamic
prefs['library_path'] = lib
dynamic.set('welcome_wizard_was_run', True)

# Auto-start the content server whenever calibre starts
# (pref lives in the GUI config, not calibre.utils.config.prefs)
from calibre.gui2 import config as gui_config
gui_config['autolaunch_server'] = True

# Content server: port 8081, authentication on
from calibre.srv.opts import change_settings
change_settings(port=8081, auth=True)

# Content-server user with write (upload) permission
from calibre.constants import config_dir
from calibre.srv.users import UserManager
m = UserManager(os.path.join(config_dir, 'server-users.sqlite'))
user, pw = os.environ['BOOTSTRAP_USER'], os.environ['BOOTSTRAP_PW']
if user not in m.all_user_names:
    m.add_user(user, pw)
print('bootstrap-ok')
"

echo "Restarting container to apply configuration ..."
docker restart calibre >/dev/null
sleep 10

# ── Verify ─────────────────────────────────────────────────────────────────────
IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"
vnc_code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8091" || true)"
srv_code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8081" || true)"
echo ""
echo "Done."
echo "  Desktop UI (VNC in browser):  http://$IP:8091   [http $vnc_code]"
echo "  Desktop UI (https):           https://$IP:8092"
echo "  Content server:               http://$IP:8081   [http $srv_code — 401 = auth working]"
echo "  Content-server login:         $CALIBRE_UPLOAD_USER / $CALIBRE_UPLOAD_PASSWORD  (stored in .env)"
echo ""
echo "Upload/download files in the desktop UI via the KasmVNC side panel (left arrow tab)."
