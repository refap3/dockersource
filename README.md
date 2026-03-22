# dockersource

A command-line tool to convert and sync Docker Compose files with Portainer stacks (Compose mode), plus a collection of ready-to-use compose files for homelab containers.

## Portainer Convert Tool

### Features

- **Convert** Docker Compose files to Portainer-safe YAML (strips `build:` directives, warns on incompatibilities)
- **Deploy** a local Compose file as a new Portainer stack
- **Update** an existing Portainer stack from a local file
- **Pull** a stack from Portainer and save it as a local `docker-compose.yml`
- **List** all stacks in Portainer
- Supports self-signed SSL certificates
- Connection settings saved to `~/.portainer-convert.json`

### Requirements

```sh
pip install pyyaml requests
```

### Setup

```sh
python3 portainer-convert.py config \
  --url https://<portainer-host>:9443 \
  --token ptr_xxxxxxxxxxxx \
  --no-verify-ssl   # if using a self-signed cert
```

### Usage

```sh
# List stacks
python3 portainer-convert.py list

# Preview conversion (stdout)
python3 portainer-convert.py to-portainer -i docker-compose.yml

# Save converted file
python3 portainer-convert.py to-portainer -i docker-compose.yml -o portainer-stack.yml

# Deploy as new stack
python3 portainer-convert.py to-portainer -i docker-compose.yml --stack-name myapp --deploy

# Update existing stack
python3 portainer-convert.py to-portainer -i docker-compose.yml --stack-name myapp --deploy --update

# Pull stack from Portainer
python3 portainer-convert.py from-portainer --stack-name myapp -o docker-compose.yml
```

### Connection options

All connection flags can be passed per-command or saved globally via `config`:

| Flag | Env var | Description |
|---|---|---|
| `--portainer-url` | `PORTAINER_URL` | Portainer base URL |
| `--token` | `PORTAINER_TOKEN` | API key (`ptr_…`) |
| `--endpoint-id` | `PORTAINER_ENDPOINT_ID` | Endpoint ID (default: 1) |
| `--no-verify-ssl` | — | Skip SSL verification |

---

## Homelab Compose Files

Each folder contains a `docker-compose.yml` (and `.env.example` where secrets are needed).

| Folder | Image | Description | Port |
|---|---|---|---|
| `portainer/` | `portainer/portainer-ce` | Container management UI | 9443, 9000 |
| `busybox/` | `busybox` | Utility shell with host filesystem access | — |
| `dozzle/` | `amir20/dozzle` | Real-time container log viewer | 8077 |
| `netalertx/` | `ghcr.io/netalertx/netalertx` | Network device monitoring & alerts | 20211 |
| `homarr/` | `ghcr.io/homarr-labs/homarr` | Homelab dashboard | 7575 |
| `sudokusolver/` | build from source | AI-powered Sudoku solver web app | 8011 |
| `ouroboros/` | `pyouroboros/ouroboros` | Automatic container image updater | — |
| `cloudflared/` | `cloudflare/cloudflared` | Cloudflare Tunnel (zero-trust ingress) | — |
| `twingate-connector/` | `twingate/connector` | Twingate zero-trust network connector | — |
| `wg-easy/` | `ghcr.io/wg-easy/wg-easy` | WireGuard VPN with web UI | 51821 |
| `filebrowser/` | `filebrowser/filebrowser` | Web UI for browsing and managing files | 8099 |

### First-run notes

- **filebrowser** — password is randomly generated on first start. Retrieve it with `docker logs filebrowser`, then change it under Settings → User Management.
- **netalertx** — on Raspberry Pi, the entrypoint `mounts.py` script fails with exit 126 (`python3: Operation not permitted`) unless `cap_add: [NET_ADMIN, NET_RAW]` and `security_opt: [seccomp:unconfined]` are set. Both are included in the compose file.

---

## Synology NAS Variants

The `synology/` folder contains Synology-specific versions of the compose files. The main differences from the Pi versions:

- Named Docker volumes are replaced with bind mounts to `/volume1/docker/<app>/`
- **filebrowser** mounts `/volume1` instead of `/` so you browse your NAS storage
- **netalertx** uses Synology's default PUID/PGID (`1026`/`100`) — verify with `id <your_username>` on your NAS

### Setup

SSH into your NAS and create the data directories:

```bash
sudo mkdir -p /volume1/docker/portainer
sudo mkdir -p /volume1/docker/netalertx
sudo mkdir -p /volume1/docker/homarr
sudo mkdir -p /volume1/docker/wg-easy
sudo mkdir -p /volume1/docker/filebrowser && sudo chmod 777 /volume1/docker/filebrowser
```

**homarr** requires a `SECRET_ENCRYPTION_KEY` before first start:

```bash
cd ~/dockersource/synology/homarr
echo "SECRET_ENCRYPTION_KEY=$(openssl rand -hex 32)" > .env
```

Clone the repo and start a container:

```bash
git clone https://github.com/refap3/dockersource
cd dockersource/synology/homarr
dcud synology/homarr/
```

### Synology container index

| Folder | Same as | Notes |
|---|---|---|
| `synology/portainer/` | `portainer/` | Bind mount for data |
| `synology/netalertx/` | `netalertx/` | Bind mount; check PUID/PGID |
| `synology/homarr/` | `homarr/` | Bind mount for appdata |
| `synology/wg-easy/` | `wg-easy/` | Bind mount; requires WireGuard kernel module |
| `synology/filebrowser/` | `filebrowser/` | Mounts `/volume1` as root; uses port 8080 internally (Synology Docker blocks port 80 binding) |

> **dozzle, ouroboros, cloudflared, twingate-connector** — no Synology variant needed, the standard compose files work as-is. Confirmed working: dozzle (`/var/run/docker.sock` path is identical on Synology DSM).

### wg-easy on Synology

WireGuard requires kernel module support. Verify before deploying:

```bash
modinfo wireguard
```

If this errors, wg-easy will not work on your NAS model.

### Containers requiring secrets

Copy `.env.example` to `.env` and fill in the values before starting:

- `homarr/` — `SECRET_ENCRYPTION_KEY` (generate with `openssl rand -hex 32`)
- `sudokusolver/` — `ANTHROPIC_API_KEY`
- `cloudflared/` — `TUNNEL_TOKEN` (from Cloudflare Zero Trust dashboard)
- `twingate-connector/` — `TWINGATE_NETWORK`, `TWINGATE_ACCESS_TOKEN`, `TWINGATE_REFRESH_TOKEN`
