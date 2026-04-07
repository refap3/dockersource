# netwatch

Home network monitor — discovers devices, tracks online/offline status, and sends alerts.

## Features

- Periodic nmap sweep + live ARP sniffing for instant detection
- Device catalog with categories (router, pc, phone, iot, nas, printer, …)
- New device alerts
- Power-on / power-off alarms per device
- Web dashboard on port 8095 with sortable columns in both tables
- Event log filterable by event type and MAC address
- Click any MAC address to cross-navigate between Devices and Events tabs
- Click any IP address to ping that host immediately and update its online status
- Notifications via webhook (ntfy, Gotify, HA), Telegram, or SMTP

## Setup

**One-liner (no repo needed):**

```bash
curl -fsSL https://raw.githubusercontent.com/refap3/dockersource/main/netwatch/install.sh | bash
```

**From the repo:**

```bash
bash netwatch/install.sh   # from repo root
bash install.sh            # from netwatch/
```

The installer creates `config.yml` from the example and stops, prompting you to set your network CIDR and interface. Re-run after editing to build and start the container.

**Update an existing installation:**

SSH into the host, then run from the `netwatch/` directory:

```bash
bash update.sh
```

This pulls the latest code from GitHub and rebuilds the container. Your `config.yml` and device database are preserved — `config.yml` is gitignored and the database lives in a named Docker volume.

Manually:

```bash
cd ~/dockersource
git pull
cd netwatch
docker compose up -d --build
```

**Fresh install — manual steps:**

```bash
cp config.yml.example config.yml
nano config.yml              # set scanner.network and scanner.interface
docker compose up -d --build
```

Dashboard: `http://<host-ip>:8095`

Requires `network_mode: host` — runs best on a Linux host (Raspberry Pi or Synology).

> `config.yml` is gitignored (like `.env`). `config.yml.example` is the committed template.

## Configuration (`config.yml`)

| Key | Default | Description |
|-----|---------|-------------|
| `scanner.network` | `192.168.1.0/24` | CIDR to scan |
| `scanner.interface` | `eth0` | Interface for ARP sniffing |
| `scanner.interval_minutes` | `5` | Nmap sweep frequency |
| `scanner.offline_threshold_minutes` | `15` | Minutes before marking device offline |
| `alarms.new_device` | `true` | Alert on unknown MAC |
| `alarms.known_device_online` | `true` | Alert when known device powers on |
| `alarms.known_device_offline` | `false` | Alert when known device goes offline |

### Static device overrides

Add known devices in `config.yml` to set persistent names/categories that survive rebuilds:

```yaml
known_devices:
  "aa:bb:cc:dd:ee:ff":
    name: "Synology NAS"
    category: "nas"
    notify_offline: true
```

### Notification channels

Enable one or more channels in `config.yml` under `notifications:`.  
All channels are disabled by default.

**Webhook** — compatible with ntfy.sh, Gotify, Home Assistant webhooks, n8n:
```yaml
notifications:
  webhook:
    enabled: true
    url: "https://ntfy.sh/my-topic"
```

**Telegram:**
```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "123456:ABC..."
    chat_id: "-100..."
```

## Categories

Auto-detected from vendor OUI lookup + hostname hints. Can be overridden in the UI or `config.yml`.

Available: `router`, `pc`, `laptop`, `phone`, `tablet`, `nas`, `printer`, `iot`, `tv`, `camera`, `other`, `unknown`

## Data

Device database is stored in Docker volume `netwatch_data` at `/app/data/netwatch.db` (SQLite).
