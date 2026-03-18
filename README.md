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
| `filebrowser/` | `filebrowser/filebrowser` | Web UI for browsing and managing files | 8080 |

### First-run notes

- **filebrowser** — password is randomly generated on first start. Retrieve it with `docker logs filebrowser`, then change it under Settings → User Management.

### Containers requiring secrets

Copy `.env.example` to `.env` and fill in the values before starting:

- `homarr/` — `SECRET_ENCRYPTION_KEY` (generate with `openssl rand -hex 32`)
- `sudokusolver/` — `ANTHROPIC_API_KEY`
- `cloudflared/` — `TUNNEL_TOKEN` (from Cloudflare Zero Trust dashboard)
- `twingate-connector/` — `TWINGATE_NETWORK`, `TWINGATE_ACCESS_TOKEN`, `TWINGATE_REFRESH_TOKEN`
