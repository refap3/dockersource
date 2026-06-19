#!/usr/bin/env bash
# generic — bootstrap any container from a docker run command
#
# Run the provider's docker run command in a second SSH session, then
# press Enter here. The script inspects the running container, generates
# docker-compose.yml + .env, and starts it via docker compose.
#
# From repo root:   bash generic/install.sh
# From this dir:    bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVOKE_DIR="$(pwd)"

echo "=== generic container bootstrap ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found." >&2; exit 1
fi
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found." >&2; exit 1
fi

# ── Ask for target folder ──────────────────────────────────────────────────────
read -r -p "Folder name for this service (will be created at $INVOKE_DIR/<name>): " FOLDER_NAME
if [[ -z "$FOLDER_NAME" ]]; then
    echo "ERROR: folder name required." >&2; exit 1
fi
TARGET_DIR="$INVOKE_DIR/$FOLDER_NAME"
mkdir -p "$TARGET_DIR"
echo "Created: $TARGET_DIR"

# ── Skip generation if compose file already exists ────────────────────────────
if [[ ! -f "$TARGET_DIR/docker-compose.yml" ]]; then

    echo ""
    echo "  1. Get the docker run command for your service."
    echo "  2. cd $TARGET_DIR"
    echo "  3. Open a second SSH session to this machine and run that command from there."
    echo "     (new terminal tab → rap $(hostname -I | awk '{print $1}' | awk -F. '{print $NF}'))"
    echo ""
    read -r -p "Press Enter once the container is running: "

    # Find the most recently started container
    TEMP="$(docker ps --latest --format '{{.Names}}')"
    if [[ -z "$TEMP" ]]; then
        echo "ERROR: no running containers found." >&2; exit 1
    fi
    echo "Found container: $TEMP — generating compose files ..."

    # Write the Python generator to a temp file (avoids pipe+heredoc conflict)
    PYFILE="$(mktemp /tmp/gen_compose.XXXXXX.py)"
    trap 'rm -f "$PYFILE"' EXIT

    cat > "$PYFILE" << 'PYEOF'
import json, sys, re, os

target_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
data = json.load(sys.stdin)[0]
cfg  = data['Config']
hcfg = data['HostConfig']

image          = cfg['Image']
raw_name       = data['Name'].lstrip('/')
service_name   = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_name)
container_name = raw_name

# Restart policy
rp      = hcfg['RestartPolicy']['Name']
restart = rp if rp else 'no'

# Env vars — skip shell internals set by the runtime, not the image
SKIP = {'PATH','HOME','HOSTNAME','TERM','SHLVL','PWD','OLDPWD','_','SHELL'}
env_vars = {}
for e in (cfg.get('Env') or []):
    if '=' in e:
        k, v = e.split('=', 1)
        if k not in SKIP:
            env_vars[k] = v

# Command / entrypoint
cmd        = cfg.get('Cmd')        or []
entrypoint = cfg.get('Entrypoint') or []

# Ports
ports = []
for cport, bindings in (hcfg.get('PortBindings') or {}).items():
    if not bindings:
        continue
    for b in bindings:
        hp    = b.get('HostPort', '')
        hip   = b.get('HostIp',   '')
        cp    = cport.replace('/tcp', '')
        proto = '/udp' if '/udp' in cport else ''
        if hip:
            ports.append(f'"{hip}:{hp}:{cp}{proto}"')
        elif hp:
            ports.append(f'"{hp}:{cp}{proto}"')
        else:
            ports.append(f'"{cp}{proto}"')

# Volumes
binds      = hcfg.get('Binds') or []
named_vols = [m for m in (data.get('Mounts') or []) if m.get('Type') == 'volume']
volumes    = list(binds)
for nv in named_vols:
    volumes.append(f"{nv['Name']}:{nv['Destination']}")

# Other options
cap_add      = hcfg.get('CapAdd')      or []
cap_drop     = hcfg.get('CapDrop')     or []
sysctls      = hcfg.get('Sysctls')     or {}
security_opt = hcfg.get('SecurityOpt') or []
privileged   = hcfg.get('Privileged',  False)
network_mode = hcfg.get('NetworkMode', 'default')
extra_hosts  = hcfg.get('ExtraHosts')  or []
devices_raw  = hcfg.get('Devices')     or []

devices = []
for d in devices_raw:
    ph = d.get('PathOnHost', '')
    pc = d.get('PathInContainer', '')
    cg = d.get('CgroupPermissions', 'rwm')
    devices.append(ph if ph == pc else f'{ph}:{pc}:{cg}')

# ── docker-compose.yml ────────────────────────────────────────────────────────
L = ['services:', f'  {service_name}:']
L.append(f'    image: {image}')
L.append(f'    container_name: {container_name}')
L.append(f'    restart: {restart}')

if privileged:
    L.append('    privileged: true')
if network_mode not in ('default', 'bridge', ''):
    L.append(f'    network_mode: {network_mode}')
if entrypoint:
    if len(entrypoint) == 1:
        L.append(f'    entrypoint: {entrypoint[0]}')
    else:
        L.append('    entrypoint:')
        for e in entrypoint: L.append(f'      - {json.dumps(e)}')
if cmd:
    if len(cmd) == 1:
        L.append(f'    command: {cmd[0]}')
    else:
        L.append('    command:')
        for c in cmd: L.append(f'      - {json.dumps(c)}')
if env_vars:
    L.append('    environment:')
    for k in sorted(env_vars): L.append(f'      - {k}=${{{k}}}')
if ports:
    L.append('    ports:')
    for p in ports: L.append(f'      - {p}')
if volumes:
    L.append('    volumes:')
    for v in volumes: L.append(f'      - {v}')
if cap_add:
    L.append('    cap_add:')
    for c in cap_add: L.append(f'      - {c}')
if cap_drop:
    L.append('    cap_drop:')
    for c in cap_drop: L.append(f'      - {c}')
if sysctls:
    L.append('    sysctls:')
    for k, v in sysctls.items(): L.append(f'      {k}: {v}')
if security_opt:
    L.append('    security_opt:')
    for s in security_opt: L.append(f'      - {s}')
if devices:
    L.append('    devices:')
    for d in devices: L.append(f'      - {d}')
if extra_hosts:
    L.append('    extra_hosts:')
    for h in extra_hosts: L.append(f'      - {h}')
if named_vols:
    L += ['', 'volumes:']
    for nv in named_vols: L.append(f'  {nv["Name"]}:')

with open(os.path.join(target_dir, 'docker-compose.yml'), 'w') as f:
    f.write('\n'.join(L) + '\n')

# ── .env ──────────────────────────────────────────────────────────────────────
env_lines = []
for k, v in sorted(env_vars.items()):
    env_lines.append(f'{k}="{v}"' if ' ' in v else f'{k}={v}')

with open(os.path.join(target_dir, '.env'), 'w') as f:
    f.write('\n'.join(env_lines) + '\n')

# Summary
print(f'  image:    {image}')
print(f'  name:     {container_name}')
if env_vars:
    print(f'  env:      {", ".join(sorted(env_vars.keys()))}')
PYEOF

    docker inspect "$TEMP" | python3 "$PYFILE" "$TARGET_DIR"

    echo "Stopping temporary container ..."
    docker stop "$TEMP" >/dev/null && docker rm "$TEMP" >/dev/null

    echo ""
    echo ">>> docker-compose.yml and .env written to $TARGET_DIR"
    echo "    Review them now if you need to make changes, then press Enter to start."
    echo ""
    read -r -p "Start the container? [Y/n] " CONFIRM
    [[ "${CONFIRM,,}" == "n" ]] && echo "cd $TARGET_DIR && docker compose up -d" && exit 0
fi

# ── Start ──────────────────────────────────────────────────────────────────────
echo "Starting container ..."
cd "$TARGET_DIR"
type dcud &>/dev/null 2>&1 || dcud() { docker compose up -d; }
dcud

echo ""
echo "Done."
