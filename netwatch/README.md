# netwatch

Home network monitor — discovers devices, tracks online/offline status, and sends alerts.

## Features

- Periodic nmap sweep + live ARP sniffing for instant detection
- Device catalog with categories (router, pc, phone, iot, nas, printer, …)
- New device alerts
- Power-on / power-off alarms per device
- Web dashboard on port 8095
- Notifications via webhook (ntfy, Gotify, HA), Telegram, or SMTP

## Setup

```bash
# 1. Copy and edit config
cp config.yml.example config.yml
nano config.yml   # set network CIDR and interface at minimum

# 2. Build and start
docker compose up -d --build

# 3. Open dashboard
http://<host-ip>:8095
```

Requires `network_mode: host` — runs best on a Linux host (Raspberry Pi or Synology).

> `config.yml` is not committed (gitignored like `.env`). `config.yml.example` is the template.

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
