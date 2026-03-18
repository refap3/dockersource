# dockersource

A command-line tool to convert and sync Docker Compose files with Portainer stacks (Compose mode).

## Features

- **Convert** Docker Compose files to Portainer-safe YAML (strips `build:` directives, warns on incompatibilities)
- **Deploy** a local Compose file as a new Portainer stack
- **Update** an existing Portainer stack from a local file
- **Pull** a stack from Portainer and save it as a local `docker-compose.yml`
- **List** all stacks in Portainer
- Supports self-signed SSL certificates
- Connection settings saved to `~/.portainer-convert.json`

## Requirements

```sh
pip install pyyaml requests
```

## Setup

```sh
python3 portainer-convert.py config \
  --url https://<portainer-host>:9443 \
  --token ptr_xxxxxxxxxxxx \
  --no-verify-ssl   # if using a self-signed cert
```

## Usage

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

## Connection options

All connection flags can be passed per-command or saved globally via `config`:

| Flag | Env var | Description |
|---|---|---|
| `--portainer-url` | `PORTAINER_URL` | Portainer base URL |
| `--token` | `PORTAINER_TOKEN` | API key (`ptr_…`) |
| `--endpoint-id` | `PORTAINER_ENDPOINT_ID` | Endpoint ID (default: 1) |
| `--no-verify-ssl` | — | Skip SSL verification |
