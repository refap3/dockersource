#!/usr/bin/env bash
# tailscale — installer
#
# From repo root:   bash tailscale/install.sh
# From service dir: bash install.sh
#
# Joins this host to the tailnet as a subnet router (host network mode):
#   - prompts for the auth key (or TS_AUTHKEY from the environment)
#   - TS_HOSTNAME defaults to $(hostname -s), TS_ROUTES to the host's LAN subnet
#   - advertises an exit node by default (TS_EXIT_NODE=0 to opt out)
#   - detects Docker's firewall backend (nftables / iptables)
#   - enables host IP forwarding via sudo if off (asks first; TS_APPLY_SYSCTL=1
#     for non-interactive use) — the container would crash-loop otherwise
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
# Optional: TS_ROUTES (advertised subnets), TS_EXTRA_ARGS (--advertise-exit-node
# by default), TS_FIREWALL_MODE (detected)
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example."
fi

# Replace KEY=... in .env in place, append if missing (temp file avoids sed -i
# portability issues)
set_env() {
    local TMP
    TMP="$(mktemp)"
    awk -v k="$1" -v v="$2" '
        index($0, k "=") == 1 { print k "=" v; done = 1; next }
        { print }
        END { if (!done) print k "=" v }
    ' .env > "$TMP"
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

# Exit node: on by default, only decided on first setup (same marker logic as
# routes). TS_EXIT_NODE=0 opts out. Advertised as 0.0.0.0/0,::/0 in TS_ROUTES —
# containerboot re-applies TS_ROUTES on every start, while TS_EXTRA_ARGS is
# ignored once the node is logged in (TS_AUTH_ONCE).
EXIT_ROUTES="0.0.0.0/0,::/0"
if ! grep -q '^# exit-node-configured' .env; then
    ROUTES="$(grep -E '^TS_ROUTES=' .env | cut -d= -f2- || true)"
    if [[ "${TS_EXIT_NODE:-1}" != "0" && "$ROUTES" != *0.0.0.0/0* ]]; then
        ROUTES="${ROUTES:+$ROUTES,}$EXIT_ROUTES"
        set_env TS_ROUTES "$ROUTES"
        echo ">>> Exit node enabled (TS_ROUTES=$ROUTES)."
    fi
    echo "# exit-node-configured" >> .env
fi

# Firewall backend: tailscale must write its rules where Docker does. On a
# mismatch Docker's FORWARD DROP policy drops all routed traffic. Detected with
# the image's own iptables-nft (no sudo needed).
FWMODE="$(grep -E '^TS_FIREWALL_MODE=' .env | cut -d= -f2- || true)"
if [[ -z "$FWMODE" ]]; then
    FWMODE="${TS_FIREWALL_MODE:-}"
    if [[ -z "$FWMODE" ]]; then
        echo "Detecting Docker's firewall backend ..."
        if docker run --rm --network host --cap-add NET_ADMIN --entrypoint iptables-nft \
               tailscale/tailscale:stable -S FORWARD 2>/dev/null | grep -q -- '-j DOCKER'; then
            FWMODE=nftables
        elif docker run --rm --network host --cap-add NET_ADMIN --entrypoint iptables-legacy \
               tailscale/tailscale:stable -S FORWARD 2>/dev/null | grep -q -- '-j DOCKER'; then
            FWMODE=iptables
        else
            FWMODE=nftables
            echo ">>> No Docker FORWARD rules found — defaulting to nftables."
        fi
    fi
    set_env TS_FIREWALL_MODE "$FWMODE"
    echo ">>> TS_FIREWALL_MODE set to $FWMODE."
fi

echo "TS_AUTHKEY and TS_HOSTNAME are set."

# ── IP forwarding ──────────────────────────────────────────────────────────────
# Subnet routes and exit node need forwarding on the host (host network mode —
# compose sysctls don't apply). Applied with sudo after asking.
ROUTES="$(grep -E '^TS_ROUTES=' .env | cut -d= -f2- || true)"
EXTRA="$(grep -E '^TS_EXTRA_ARGS=' .env | cut -d= -f2- || true)"
EXIT_NODE=0
[[ "$ROUTES" == *0.0.0.0/0* || "$EXTRA" == *advertise-exit-node* ]] && EXIT_NODE=1
# Subnet routes only, for the summary
ROUTES="$(echo "$ROUTES" | tr ',' '\n' | grep -vxE '0\.0\.0\.0/0|::/0' | paste -sd, - || true)"
# The container tries to enable forwarding for every address family in
# TS_ROUTES and crash-loops if it can't (/proc/sys is read-only in it), so a
# missing sysctl is fatal here. The exit node (0.0.0.0/0,::/0) needs both.
ALL_ROUTES="$(grep -E '^TS_ROUTES=' .env | cut -d= -f2- || true)"
NEED4=0; NEED6=0
[[ "$ALL_ROUTES" == *.*/* ]] && NEED4=1
[[ "$ALL_ROUTES" == *:*/* ]] && NEED6=1
fwd_ok() {
    V4="$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo 0)"
    V6="$(cat /proc/sys/net/ipv6/conf/all/forwarding 2>/dev/null || echo 0)"
    [[ ! ( ( "$NEED4" == "1" && "$V4" != "1" ) || ( "$NEED6" == "1" && "$V6" != "1" ) ) ]]
}
if ! fwd_ok; then
    IF="$(ip route show default 2>/dev/null | awk '{for (i=1;i<NF;i++) if ($i=="dev") {print $(i+1); exit}}' || true)"
    SYSCTL_FILE=/etc/sysctl.d/99-tailscale.conf
    # With forwarding on, Linux ignores router advertisements unless
    # accept_ra=2 — the host would lose its SLAAC IPv6 address.
    SYSCTL_CONF="net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.${IF:-eth0}.accept_ra = 2"
    echo ""
    echo ">>> IP forwarding is off (ipv4=$V4 ipv6=$V6) — the container would crash-loop."
    echo "    Needed in $SYSCTL_FILE:"
    echo "$SYSCTL_CONF" | sed 's/^/      /'
    # Interactive: ask. Non-interactive: TS_APPLY_SYSCTL=1 applies via sudo -n.
    APPLY="${TS_APPLY_SYSCTL:-}"
    if [[ -z "$APPLY" && -t 0 ]]; then
        read -r -p "Write $SYSCTL_FILE and apply it now with sudo? [Y/n]: " APPLY
        [[ "$APPLY" =~ ^[Nn] ]] && APPLY=0 || APPLY=1
    fi
    if [[ "$APPLY" == "1" ]] && command -v sudo &>/dev/null; then
        SUDO=sudo
        [[ -t 0 ]] || SUDO="sudo -n"
        if echo "$SYSCTL_CONF" | $SUDO tee "$SYSCTL_FILE" >/dev/null \
           && $SUDO sysctl -p "$SYSCTL_FILE" >/dev/null; then
            echo ">>> $SYSCTL_FILE written and applied."
        fi
    fi
    if ! fwd_ok; then
        echo "" >&2
        echo "ERROR: IP forwarding still off (ipv4=$V4 ipv6=$V6). Write the lines above to" >&2
        echo "       $SYSCTL_FILE, run: sudo sysctl -p $SYSCTL_FILE — then re-run." >&2
        echo "       Or drop the exit node: remove 0.0.0.0/0,::/0 from TS_ROUTES in .env." >&2
        exit 1
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
    # Match the IP itself — docker exec prints errors on stdout while restarting
    TSIP="$(docker exec tailscale tailscale ip -4 2>/dev/null | grep -E '^100\.' | head -1 || true)"
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
if [[ -n "$ROUTES" || "$EXIT_NODE" == "1" ]]; then
    WHAT="${ROUTES:+routes ($ROUTES)}"
    [[ "$EXIT_NODE" == "1" ]] && WHAT="${WHAT:+$WHAT + }exit node"
    echo "  Approve $WHAT:"
    echo "  https://login.tailscale.com/admin/machines → $TSHOST → Edit route settings"
fi
echo "  Status: docker exec tailscale tailscale status"
