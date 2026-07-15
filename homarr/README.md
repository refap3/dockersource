# homarr

Homelab dashboard ([homarr-labs/homarr](https://github.com/homarr-labs/homarr)), port 7575.

## Install

```bash
bash install.sh
```

`SECRET_ENCRYPTION_KEY` is generated and written to `.env` without any manual step (openssl if available, `/dev/urandom` fallback otherwise). The key encrypts stored integration credentials: generate once, never change it.

The script then **prompts for an admin username and password** and creates the account directly in the DB (`create-admin.js` — bcrypt-hashed password, `credentials-admin` group with admin permission, `everyone` membership; exactly what the wizard's user step writes). The web onboarding wizard is skipped entirely: after install, log in straight away, then run `findtargetcontainers.sh` (below) to populate the board.

- Non-interactive installs: set `HOMARR_ADMIN_USER` and `HOMARR_ADMIN_PASSWORD`. Without a TTY and without these variables the admin step is skipped — rerun `install.sh` interactively later; it is idempotent and never touches an existing user.
- Why not the web wizard? A browser tab left open from a previous homarr instance replays its wizard state against a new instance the moment it comes up, silently advancing onboarding to `finish` **without the user-creation step** — you end up at a login screen with no valid credentials. Creating the admin at install time avoids that entirely.

**Troubleshooting: login says "welcome back" but no credentials work** (install predating `create-admin.js` that hit the stale-tab issue — `onboarding` at `finish`, `user` table empty). Rerun `bash install.sh`, or reset the wizard to the user-creation step and reload the page:

```bash
docker exec homarr node -e '
const db = require("better-sqlite3")("/appdata/db/db.sqlite");
db.prepare("UPDATE onboarding SET step = ?, previous_step = ?").run("user", "start");'
docker restart homarr
```

**Full reset (wipe all homarr data):**

```bash
docker compose down -v && bash install.sh
```

## Auto-populate the dashboard: `findtargetcontainers.sh`

```bash
bash findtargetcontainers.sh [--dry-run] [--all] [--board <name>] [--container <homarr-container>] [--keep-defaults] [--keep-private]
```

Scans the Docker containers on this node and mirrors them as app tiles on the default homarr board (the server-wide home board, or `--board <name>`):

- **new containers** are added — tile name, URL derived from the published ports, icon from the [dashboard-icons](https://github.com/walkxcode/dashboard-icons) CDN (generic Docker icon as fallback)
- **removed containers** disappear from the board on the next run
- **changed URLs/icons** are updated
- **onboarding wizard leftovers are pruned** — the sample links (Homarr Docs, Homarr GitHub, Help Translate, Support Homarr; matched on exact name *and* URL), the tiles from the wizard's "import from Docker" step (no description, broken `http://socket:<port>` URL or duplicate of a managed container tile), and the wizard's default widgets (Archive Team Warrior, clock, weather, bookmarks). Widgets are pruned only **once** per install (flag file `ftc-wizard-widgets-pruned` in the `homarr_appdata` volume), so identical widgets you add later survive. Pass `--keep-defaults` to keep everything; tiles you created yourself are never removed

The target board is also **made public** — without this, devices without a login session (phones, TVs) only see homarr's login page. Public means anyone on the LAN can *view* the board (tiles, widgets, internal service URLs); editing still requires an account. Pass `--keep-private` to leave visibility untouched. Don't port-forward homarr with a public board.

After every sync the board is **compacted**: gaps left by removed tiles disappear and all tiles are repacked top-left in their existing reading order (this also repositions manually placed tiles on the synced board).

Re-run any time (idempotent), e.g. from cron. Only tiles the script created itself are managed — it tags them in the app description and never touches manually created apps. The homarr SQLite DB is backed up to `db.sqlite.ftc-backup` (inside the `homarr_appdata` volume) before every write, and changes show up on the next browser reload — no container restart needed.

### Flags

| Flag | Effect |
|---|---|
| `--dry-run` | show what would change, write nothing |
| `--all` | include stopped containers (default: running only) |
| `--board NAME` | sync onto this board instead of the home board |
| `--container NAME` | homarr container name (default: auto-detected by image) |
| `--keep-defaults` | keep the wizard's leftover tiles (default: prune them) |
| `--keep-private` | leave board visibility untouched (default: make it public so it is viewable without login) |

### Per-container overrides (docker labels)

| Label | Effect |
|---|---|
| `homarr.ignore=true` | never add this container |
| `homarr.url=<url>` | use this URL for the tile (needed for `network_mode: host` containers, or when the port heuristic picks the wrong port) |
| `homarr.icon=<url>` | use this icon |

URL heuristic: container port 80 → 443 → 8080 → 3000 → 9443/8443 (https) → lowest port ≥ 1000. Containers without published ports get a tile without a link.

### Built-in special cases

Hardcoded in `sync-homarr-apps.js` (docker labels still win over these):

| Container | Behavior |
|---|---|
| `twingate*`, `cloudflared`, `portainer-agent`/`portainer_agent` | background/infrastructure containers — never get a tile |
| `calibre` | tile URL is the **https** web UI `https://<host>:8092/` (the http one only works behind a TLS proxy); an extra tile **calibre content** → `http://<host>:8081/` is added |
| `netwatch` | tile URL `http://<host>:8095/` — runs in host network mode, so no published ports to derive a URL from |
| `marcujump` | extra tile **marcujump handbuch** → `http://<host>:8093/MarcuJumpGuide.html` |
| `FlashForgeAdventurer5MAPI` | tile URL `http://<host>:9876/en/<printer-ip>` — the printer IP comes from the container's `flashforge.printer_ip` docker label, set by `flashforge/install.sh` |

Extra tiles are managed like normal container tiles: they appear when the parent container exists and are removed when it's gone.

### How it works

`findtargetcontainers.sh` runs on the Docker host; the actual sync (`sync-homarr-apps.js`) executes inside the homarr container via `docker exec`, using the container's node runtime, the mounted `/var/run/docker.sock` for the scan, and better-sqlite3 for direct writes to `/appdata/db/db.sqlite` (homarr's public API has no board endpoints).
