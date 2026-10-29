#!/usr/bin/env bash
# tailscale — installer
#
# From repo root:   bash tailscale/install.sh
# From service dir: bash install.sh
#
# Joins this host to the tailnet as a subnet router (host network mode):
#   - prompts for the auth key (or TS_AUTHKEY from the environment)
#   - TS_HOSTNAME defaults to $(hostname -s), TS_ROUTES to the host's LAN subnet
#   - checks IP forwarding (required for subnet routes / exit node)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== tailscale — install ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker and try again." >&2
    exit 1
fi

if [[ ! -c /dev/net/tun ]]; then
    echo "ERROR: /dev/net/tun not found — the tun kernel module is required." >&2
    echo "       Try: sudo modprobe tun" >&2
    exit 1
fi

# ── Configuration ──────────────────────────────────────────────────────────────
# Required in .env:
#   TS_AUTHKEY  — only used for the first login, then the state volume is enough
#   TS_HOSTNAME — machine name in the tailnet
# Optional: TS_ROUTES (advertised subnets), TS_EXTRA_ARGS (e.g. --advertise-exit-node)
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

# Replace KEY=... in .env (temp file avoids sed -i portability issues)
set_env() {
    local TMP
    TMP="$(mktemp)"
    grep -v "^$1=" .env > "$TMP" || true
    echo "$1=$2" >> "$TMP"
    mv "$TMP" .env
}

AUTHKEY="$(grep -E '^TS_AUTHKEY=' .env | cut -d= -f2- || true)"
if [[ -z "$AUTHKEY" || "$AUTHKEY" == "tskey-auth-your-key-here" ]]; then
    AUTHKEY="${TS_AUTHKEY:-}"
    if [[ -z "$AUTHKEY" ]]; then
        if [[ ! -t 0 ]]; then
            echo "ERROR: no TTY and TS_AUTHKEY not set." >&2
            exit 1
        fi
        echo ""
        echo "  Generate an auth key in the Tailscale admin console:"
        echo "     https://login.tailscale.com/admin/settings/keys → Generate auth key"
        echo "     (reusable not needed; pre-approved recommended if device approval is on)"
        echo ""
        read -r -s -p "Paste auth key (tskey-auth-...): " AUTHKEY; echo
    fi
    if [[ "$AUTHKEY" != tskey-* ]]; then
        echo "ERROR: auth key must start with 'tskey-'." >&2
        exit 1
    fi
    set_env TS_AUTHKEY "$AUTHKEY"
    echo ">>> TS_AUTHKEY written to .env."
fi

TSHOST="$(grep -E '^TS_HOSTNAME=' .env | cut -d= -f2- || true)"
if [[ -z "$TSHOST" || "$TSHOST" == "your-hostname" ]]; then
    TSHOST="${TS_HOSTNAME:-$(hostname -s)}"
    set_env TS_HOSTNAME "$TSHOST"
    echo ">>> TS_HOSTNAME set to $TSHOST."
fi

# Routes: only filled on first setup; an intentionally empty value is kept
# once the marker line exists.
if ! grep -q '^# routes-configured' .env; then
    # LAN subnet of the default-route interface, e.g. 192.168.1.0/24
    DEFAULT_IF="$(ip route show default 2>/dev/null | awk '{for (i=1;i<NF;i++) if ($i=="dev") {print $(i+1); exit}}' || true)"
    LAN="$(ip -o -f inet route show dev "${DEFAULT_IF:-eth0}" scope link 2>/dev/null | awk '{print $1; exit}' || true)"
    ROUTES="${TS_ROUTES-$LAN}"
    if [[ -t 0 && -z "${TS_ROUTES+x}" ]]; then
        read -r -p "Subnet routes to advertise (comma-separated, '-' = none) [${LAN:--}]: " INPUT
        [[ -n "$INPUT" ]] && ROUTES="$INPUT"
    fi
    [[ "$ROUTES" == "-" ]] && ROUTES=""
    set_env TS_ROUTES "$ROUTES"
    echo "# routes-configured" >> .env
    echo ">>> TS_ROUTES set to '${ROUTES}'."
fi

echo "TS_AUTHKEY and TS_HOSTNAME are set."

# ── IP forwarding ──────────────────────────────────────────────────────────────
# Subnet routes and exit node need forwarding on the host (host network mode —
# compose sysctls don't apply). Not changed automatically: needs sudo.
ROUTES="$(grep -E '^TS_ROUTES=' .env | cut -d= -f2- || true)"
EXTRA="$(grep -E '^TS_EXTRA_ARGS=' .env | cut -d= -f2- || true)"
if [[ -n "$ROUTES" || "$EXTRA" == *advertise-exit-node* ]]; then
    if [[ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo 0)" != "1" ]]; then
        echo ""
        echo "WARNING: IP forwarding is off — subnet routes will not work." >&2
        echo "         Enable it permanently with:" >&2
        echo "           echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-tailscale.conf" >&2
        echo "           echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf" >&2
        echo "           sudo sysctl -p /etc/sysctl.d/99-tailscale.conf" >&2
        echo ""
    fi
fi

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting tailscale ..."
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

# ── Verify ─────────────────────────────────────────────────────────────────────
echo "Waiting for tailscale to log in ..."
TSIP=""
for _ in $(seq 1 30); do
    TSIP="$(docker exec tailscale tailscale ip -4 2>/dev/null | head -1 || true)"
    [[ -n "$TSIP" ]] && break
    sleep 2
done
if [[ -z "$TSIP" ]]; then
    echo "ERROR: tailscale did not come up. Check: docker logs tailscale" >&2
    echo "       Expired or already-used auth key? Clear TS_AUTHKEY in .env and re-run." >&2
    exit 1
fi

echo ""
echo "Done. $TSHOST is in the tailnet as $TSIP"
if [[ -n "$ROUTES" ]]; then
    echo "  Approve the advertised routes ($ROUTES):"
    echo "  https://login.tailscale.com/admin/machines → $TSHOST → Edit route settings"
fi
echo "  Status: docker exec tailscale tailscale status"
