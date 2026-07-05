# homarr

Homelab dashboard ([homarr-labs/homarr](https://github.com/homarr-labs/homarr)), port 7575.

## Install

```bash
bash install.sh
```

Fully automatic — `SECRET_ENCRYPTION_KEY` is generated and written to `.env` without any manual step (openssl if available, `/dev/urandom` fallback otherwise). The key encrypts stored integration credentials: generate once, never change it.

### First start: onboarding wizard

Open `http://<host>:7575` and walk through the wizard **before** running the sync script:

1. **Setup mode** — pick **"Start from scratch"** (import is only for homarr < 1.0 configs, restore for a SQLite backup).
2. **Create the admin user** — this is the only place credentials are set; there is no default username/password.
3. Remaining steps (group, settings, integrations) — click through as you like. **Skip the "import from Docker" step** — `findtargetcontainers.sh` handles that better (correct URLs, auto-updates); imported tiles would be pruned on the first sync run anyway.

Then run `findtargetcontainers.sh` (below) to populate the board.

**Troubleshooting: login says "welcome back" but no credentials work.** The wizard finished without creating a user (`onboarding` table at `finish`, `user` table empty). Reset the wizard to the user-creation step and reload the page:

```bash
docker exec homarr node -e '
const db = require("better-sqlite3")("/appdata/db/db.sqlite");
db.prepare("UPDATE onboarding SET step = ?, previous_step = ?").run("user", "start");'
docker restart homarr
```

**Full reset (wipe all homarr data, back to the wizard):**

```bash
docker compose down -v && bash install.sh
```

## Auto-populate the dashboard: `findtargetcontainers.sh`

```bash
bash findtargetcontainers.sh [--dry-run] [--all] [--board <name>] [--container <homarr-container>] [--keep-defaults]
```

Scans the Docker containers on this node and mirrors them as app tiles on the default homarr board (the server-wide home board, or `--board <name>`):

- **new containers** are added — tile name, URL derived from the published ports, icon from the [dashboard-icons](https://github.com/walkxcode/dashboard-icons) CDN (generic Docker icon as fallback)
- **removed containers** disappear from the board on the next run
- **changed URLs/icons** are updated
- **onboarding wizard leftovers are pruned** — the sample links (Homarr Docs, Homarr GitHub, Help Translate, Support Homarr; matched on exact name *and* URL), the tiles from the wizard's "import from Docker" step (no description, broken `http://socket:<port>` URL or duplicate of a managed container tile), and the wizard's default widgets (Archive Team Warrior, clock, weather, bookmarks). Widgets are pruned only **once** per install (flag file `ftc-wizard-widgets-pruned` in the `homarr_appdata` volume), so identical widgets you add later survive. Pass `--keep-defaults` to keep everything; tiles you created yourself are never removed

Re-run any time (idempotent), e.g. from cron. Only tiles the script created itself are managed — it tags them in the app description and never touches manually created apps. The homarr SQLite DB is backed up to `db.sqlite.ftc-backup` (inside the `homarr_appdata` volume) before every write, and changes show up on the next browser reload — no container restart needed.

### Flags

| Flag | Effect |
|---|---|
| `--dry-run` | show what would change, write nothing |
| `--all` | include stopped containers (default: running only) |
| `--board NAME` | sync onto this board instead of the home board |
| `--container NAME` | homarr container name (default: auto-detected by image) |
| `--keep-defaults` | keep the wizard's leftover tiles (default: prune them) |

### Per-container overrides (docker labels)

| Label | Effect |
|---|---|
| `homarr.ignore=true` | never add this container |
| `homarr.url=<url>` | use this URL for the tile (needed for `network_mode: host` containers, or when the port heuristic picks the wrong port) |
| `homarr.icon=<url>` | use this icon |

URL heuristic: container port 80 → 443 → 8080 → 3000 → 9443/8443 (https) → lowest port ≥ 1000. Containers without published ports get a tile without a link.

### How it works

`findtargetcontainers.sh` runs on the Docker host; the actual sync (`sync-homarr-apps.js`) executes inside the homarr container via `docker exec`, using the container's node runtime, the mounted `/var/run/docker.sock` for the scan, and better-sqlite3 for direct writes to `/appdata/db/db.sqlite` (homarr's public API has no board endpoints).
