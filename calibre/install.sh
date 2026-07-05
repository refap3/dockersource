#!/usr/bin/env bash
# calibre — installer
#
# From repo root:   bash calibre/install.sh
# From service dir: bash install.sh
#
# Starts the container, then bootstraps it for immediate use:
#   - creates the library at /config/Calibre Library
#   - skips the welcome wizard
#   - enables the content server on port 8081 (auto-starts with calibre, no authentication,
#     uploads allowed from the LAN via trusted_ips)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== calibre — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
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
docker exec -u abc -e HOME=/config calibre calibre-debug -c "
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

# Content server: port 8081, no authentication (LAN-open; do not expose to WAN).
# trusted_ips lets un-authenticated LAN clients upload/change books;
# 172.16.0.0/12 covers the docker bridge so host-local requests work too.
from calibre.srv.opts import change_settings
change_settings(port=8081, auth=False, trusted_ips='192.168.1.0/24,172.16.0.0/12,127.0.0.1')
print('bootstrap-ok')
"

echo "Restarting container to apply configuration ..."
docker restart calibre >/dev/null
sleep 10

# ── Verify ─────────────────────────────────────────────────────────────────────
IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"
vnc_code="$(curl -sk -o /dev/null -w '%{http_code}' "https://localhost:8092" || true)"
srv_code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8081" || true)"
echo ""
echo "Done."
echo "  Desktop UI (in browser):  https://$IP:8092   [https $vnc_code]"
echo "      HTTPS only — accept the self-signed certificate warning once."
echo "      (http port 8091 is refused by the streaming stack unless behind a TLS proxy)"
echo "  Content server:           http://$IP:8081   [http $srv_code]  (no login, LAN uploads enabled — do not port-forward)"
echo ""
echo "Upload/download files in the desktop UI via the side panel (left arrow tab)."
