// sync-homarr-apps.js — executed INSIDE the homarr container by
// findtargetcontainers.sh (docker exec ... node < sync-homarr-apps.js).
//
// Scans the local Docker node via the mounted /var/run/docker.sock, then
// syncs the containers as app tiles onto the default homarr board:
//   - new containers   -> app + board item created
//   - gone containers  -> app + board item removed
//   - changed URL/icon -> app updated
//
// Only apps whose description starts with the MARKER are ever touched, so
// manually created tiles are left alone.
//
// Environment (set by the wrapper script):
//   FTC_HOST_IP        IP used to build container URLs (required)
//   FTC_BOARD          board name to sync onto (default: server home board)
//   FTC_DRY_RUN        "1" = report only, no writes
//   FTC_INCLUDE_STOPPED "1" = include stopped containers
//   FTC_KEEP_DEFAULTS  "1" = keep the wizard's leftover tiles (default: prune them)
//
// Per-container overrides via docker labels:
//   homarr.ignore=true   skip this container
//   homarr.url=<url>     use this URL instead of the derived one
//   homarr.icon=<url>    use this icon instead of the derived one
//
// Built-in special cases (BACKGROUND_CONTAINERS / SPECIAL_CASES below):
// background containers get no tile; some containers get a URL override
// and/or extra tiles that are added/removed together with the container.

const http = require("http");
const https = require("https");
const os = require("os");
const fs = require("fs");

const MARKER = "Auto-added by findtargetcontainers.sh from container: ";
const HOST_IP = process.env.FTC_HOST_IP;
const DRY_RUN = process.env.FTC_DRY_RUN === "1";
const INCLUDE_STOPPED = process.env.FTC_INCLUDE_STOPPED === "1";
const KEEP_DEFAULTS = process.env.FTC_KEEP_DEFAULTS === "1";
// Sample tiles the onboarding wizard creates; pruned unless --keep-defaults.
// Matched on exact name AND URL so user-created apps are never touched.
const WIZARD_APPS = new Map([
  ["Homarr Docs", "https://homarr.dev/docs/getting-started"],
  ["Homarr GitHub", "https://github.com/homarr-labs/homarr"],
  ["Help Translate", "https://homarr.dev/docs/community/translations"],
  ["Support Homarr", "https://opencollective.com/homarr"],
]);
// Widgets the wizard puts on the first board. Pruned only ONCE per install
// (flag file below), so identical widgets the user adds later survive.
const WIZARD_WIDGET_KINDS = ["archiveTeamWarrior", "clock", "weather", "bookmarks"];
const WIZARD_WIDGET_FLAG = "/appdata/ftc-wizard-widgets-pruned";
// Infrastructure/background containers that never get a tile.
const BACKGROUND_CONTAINERS = [
  /^twingate/i,
  /^cloudflared?/i,
  /^portainer[-_]?agent/i,
];
// Per-container special cases: URL overrides and extra tiles that live and
// die with their parent container. URLs are templates with {ip} placeholder.
const SPECIAL_CASES = {
  calibre: {
    // 8092 is the https web UI; the http one (8091) only works behind TLS proxy
    url: "https://{ip}:8092/",
    extras: [
      {
        suffix: "content",
        title: "calibre content",
        url: "http://{ip}:8081/",
      },
    ],
  },
  netwatch: {
    // host network mode — no published ports to derive a URL from
    url: "http://{ip}:8095/",
  },
  marcujump: {
    extras: [
      {
        suffix: "handbuch",
        title: "marcujump handbuch",
        url: "http://{ip}:8093/MarcuJumpGuide.html",
      },
    ],
  },
};
const ICON_CDN = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/";
const FALLBACK_ICON = ICON_CDN + "docker.png";
const HTTPS_CONTAINER_PORTS = new Set([443, 8443, 9443]);
const WEB_PORT_MIN = 1000;

if (!HOST_IP) {
  console.error("ERROR: FTC_HOST_IP not set");
  process.exit(1);
}

function dockerGet(path) {
  return new Promise((resolve, reject) => {
    http
      .get({ socketPath: "/var/run/docker.sock", path, headers: { Host: "docker" } }, (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => {
          if (res.statusCode >= 300) reject(new Error(path + " -> HTTP " + res.statusCode));
          else resolve(JSON.parse(data));
        });
      })
      .on("error", reject);
  });
}

function iconExists(url) {
  return new Promise((resolve) => {
    const req = https.request(url, { method: "HEAD", timeout: 5000 }, (res) =>
      resolve(res.statusCode === 200)
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.end();
  });
}

// cuid2-style id like homarr generates: lowercase letter + 23 [a-z0-9]
function newId() {
  const alpha = "abcdefghijklmnopqrstuvwxyz";
  const alnum = alpha + "0123456789";
  let id = alpha[Math.floor(Math.random() * 26)];
  for (let i = 0; i < 23; i++) id += alnum[Math.floor(Math.random() * 36)];
  return id;
}

// Pick the most likely web UI port. Preference tiers:
//   1. container port 80, then 443
//   2. common web ports (8080, 3000)
//   3. https admin ports (9443, 8443)
//   4. lowest container port >= 1000, else lowest published host port
function pickUrl(ports) {
  const tcp = ports.filter((p) => p.Type === "tcp" && p.PublicPort);
  if (tcp.length === 0) return null;
  const scheme = (p) => (HTTPS_CONTAINER_PORTS.has(p.PrivatePort) ? "https" : "http");
  const byPrivate = (want) => tcp.find((p) => p.PrivatePort === want);
  const chosen =
    byPrivate(80) ||
    byPrivate(443) ||
    byPrivate(8080) ||
    byPrivate(3000) ||
    byPrivate(9443) ||
    byPrivate(8443) ||
    tcp
      .filter((p) => p.PrivatePort >= WEB_PORT_MIN)
      .sort((a, b) => a.PrivatePort - b.PrivatePort)[0] ||
    tcp.sort((a, b) => a.PublicPort - b.PublicPort)[0];
  return scheme(chosen) + "://" + HOST_IP + ":" + chosen.PublicPort;
}

async function pickIcon(name, image) {
  const candidates = [];
  const clean = name.toLowerCase().replace(/[-_][0-9]+$/, "");
  candidates.push(clean);
  const imageBase = image.split("/").pop().split(":")[0].toLowerCase();
  if (imageBase !== clean) candidates.push(imageBase);
  for (const c of candidates) {
    const url = ICON_CDN + c + ".png";
    if (await iconExists(url)) return url;
  }
  return FALLBACK_ICON;
}

async function scanContainers() {
  const list = await dockerGet("/containers/json" + (INCLUDE_STOPPED ? "?all=true" : ""));
  const self = process.env.FTC_SELF || os.hostname();
  const result = [];
  for (const c of list) {
    const name = (c.Names[0] || "").replace(/^\//, "");
    if (!name) continue;
    // skip homarr itself (FTC_SELF = container name, set by the wrapper)
    if (name === self || c.Id.startsWith(self)) continue;
    if (BACKGROUND_CONTAINERS.some((re) => re.test(name))) continue;
    const labels = c.Labels || {};
    if (labels["homarr.ignore"] === "true") continue;
    const special = SPECIAL_CASES[name];
    const specialUrl = special && special.url ? special.url.replace("{ip}", HOST_IP) : null;
    const url = labels["homarr.url"] || specialUrl || pickUrl(c.Ports || []);
    const icon = labels["homarr.icon"] || (await pickIcon(name, c.Image || ""));
    // tile title: compose service name reads nicer than "project-service-1"
    const title = labels["com.docker.compose.service"] || name;
    result.push({ name, title, url, icon });
    // extra tiles tied to this container (added/removed together with it)
    if (special && special.extras) {
      for (const e of special.extras) {
        result.push({
          name: name + "/" + e.suffix,
          title: e.title,
          url: e.url.replace("{ip}", HOST_IP),
          icon: e.icon || icon,
        });
      }
    }
  }
  return result;
}

function main(containers) {
  const db = require("better-sqlite3")("/appdata/db/db.sqlite");
  db.pragma("busy_timeout = 5000");

  // Target board: FTC_BOARD by name, else the server-wide home board, else first board
  let board;
  if (process.env.FTC_BOARD) {
    board = db.prepare("SELECT * FROM board WHERE name = ?").get(process.env.FTC_BOARD);
    if (!board) throw new Error("board not found: " + process.env.FTC_BOARD);
  } else {
    const setting = db
      .prepare("SELECT value FROM serverSetting WHERE setting_key = 'board'")
      .get();
    const homeId = setting ? JSON.parse(setting.value).json.homeBoardId : null;
    board = homeId ? db.prepare("SELECT * FROM board WHERE id = ?").get(homeId) : null;
    if (!board) board = db.prepare("SELECT * FROM board LIMIT 1").get();
    if (!board) throw new Error("no board exists yet — create one in the homarr UI first");
  }
  const section = db
    .prepare("SELECT * FROM section WHERE board_id = ? ORDER BY y_offset LIMIT 1")
    .get(board.id);
  if (!section) throw new Error("board '" + board.name + "' has no section");
  const layouts = db.prepare("SELECT * FROM layout WHERE board_id = ?").all(board.id);

  const managed = db
    .prepare("SELECT * FROM app WHERE description LIKE ?")
    .all(MARKER + "%");
  const managedByName = new Map(
    managed.map((a) => [a.description.slice(MARKER.length), a])
  );
  const seen = new Set();
  const report = { added: [], removed: [], pruned: [], updated: [], unchanged: [] };

  const deleteAppWithItems = (app) => {
    const items = db
      .prepare("SELECT id, options FROM item WHERE kind = 'app'")
      .all()
      .filter((i) => {
        try {
          return JSON.parse(i.options).json.appId === app.id;
        } catch {
          return false;
        }
      });
    for (const i of items) db.prepare("DELETE FROM item WHERE id = ?").run(i.id);
    db.prepare("DELETE FROM app WHERE id = ?").run(app.id);
  };

  // Wizard leftovers: the sample links (exact name+URL match) plus tiles from
  // the onboarding "import from Docker" step — those have no description and
  // either a broken http://socket:<port> URL or no URL at all while the
  // container is one this script already manages.
  const containerNames = new Set(containers.map((c) => c.name));
  const findWizardApps = () =>
    db.prepare("SELECT * FROM app").all().filter(
      (a) =>
        WIZARD_APPS.get(a.name) === a.href ||
        (!a.description &&
          (/^https?:\/\/socket[:/]/.test(a.href || "") ||
            (!a.href && containerNames.has(a.name))))
    );

  const pruneWidgets = !KEEP_DEFAULTS && !fs.existsSync(WIZARD_WIDGET_FLAG);
  const findWizardWidgets = () =>
    db
      .prepare(
        "SELECT id, kind FROM item WHERE kind IN (" +
          WIZARD_WIDGET_KINDS.map(() => "?").join(",") +
          ")"
      )
      .all(...WIZARD_WIDGET_KINDS);

  const sync = db.transaction(() => {
    // next free row per layout in the target section
    const nextY = {};
    const counter = {};
    for (const l of layouts) {
      const row = db
        .prepare(
          "SELECT COALESCE(MAX(y_offset + height), 0) AS y FROM item_layout WHERE section_id = ? AND layout_id = ?"
        )
        .get(section.id, l.id);
      nextY[l.id] = row.y;
      counter[l.id] = 0;
    }

    for (const c of containers) {
      seen.add(c.name);
      const existing = managedByName.get(c.name);
      if (existing) {
        if (existing.href !== c.url || existing.icon_url !== c.icon) {
          db.prepare("UPDATE app SET href = ?, ping_url = ?, icon_url = ? WHERE id = ?").run(
            c.url,
            c.url,
            c.icon,
            existing.id
          );
          report.updated.push(c.name);
        } else {
          report.unchanged.push(c.name);
        }
        continue;
      }
      // new app + board item
      const appId = newId();
      db.prepare(
        "INSERT INTO app (id, name, description, icon_url, href, ping_url) VALUES (?, ?, ?, ?, ?, ?)"
      ).run(appId, c.title, MARKER + c.name, c.icon, c.url, c.url);
      const itemId = newId();
      const options = JSON.stringify({
        json: {
          appId,
          openInNewTab: true,
          pingEnabled: Boolean(c.url),
          showTitle: true,
          layout: "column",
          descriptionDisplayMode: "tooltip",
        },
      });
      db.prepare(
        "INSERT INTO item (id, board_id, kind, options, advanced_options) VALUES (?, ?, 'app', ?, '{\"json\": {}}')"
      ).run(itemId, board.id, options);
      for (const l of layouts) {
        const x = counter[l.id] % l.column_count;
        const y = nextY[l.id] + Math.floor(counter[l.id] / l.column_count);
        counter[l.id]++;
        db.prepare(
          "INSERT INTO item_layout (item_id, section_id, layout_id, x_offset, y_offset, width, height) VALUES (?, ?, ?, ?, ?, 1, 1)"
        ).run(itemId, section.id, l.id, x, y);
      }
      report.added.push(c.name + (c.url ? " -> " + c.url : " (no published port)"));
    }

    // remove managed apps whose container is gone (item cascade-deletes its layouts)
    for (const [name, app] of managedByName) {
      if (seen.has(name)) continue;
      deleteAppWithItems(app);
      report.removed.push(name);
    }

    // prune the wizard's sample tiles (Homarr Docs, GitHub, ...)
    if (!KEEP_DEFAULTS) {
      for (const app of findWizardApps()) {
        deleteAppWithItems(app);
        report.pruned.push(app.name);
      }
    }

    // prune the wizard's widgets, once per install
    if (pruneWidgets) {
      for (const w of findWizardWidgets()) {
        db.prepare("DELETE FROM item WHERE id = ?").run(w.id);
        report.pruned.push("widget: " + w.kind);
      }
    }

    // compact: removed tiles leave holes — repack everything top-left,
    // preserving the existing reading order (by row, then column)
    for (const l of layouts) {
      const placed = db
        .prepare(
          "SELECT item_id, width, height FROM item_layout WHERE section_id = ? AND layout_id = ? ORDER BY y_offset, x_offset"
        )
        .all(section.id, l.id);
      let x = 0,
        y = 0,
        rowHeight = 1;
      for (const p of placed) {
        const w = Math.min(p.width, l.column_count);
        if (x + w > l.column_count) {
          x = 0;
          y += rowHeight;
          rowHeight = 1;
        }
        db.prepare(
          "UPDATE item_layout SET x_offset = ?, y_offset = ? WHERE item_id = ? AND section_id = ? AND layout_id = ?"
        ).run(x, y, p.item_id, section.id, l.id);
        x += w;
        rowHeight = Math.max(rowHeight, p.height);
      }
    }
  });

  if (DRY_RUN) {
    // simulate the diff without writing
    for (const c of containers) {
      seen.add(c.name);
      const existing = managedByName.get(c.name);
      if (!existing) report.added.push(c.name + (c.url ? " -> " + c.url : " (no published port)"));
      else if (existing.href !== c.url || existing.icon_url !== c.icon) report.updated.push(c.name);
      else report.unchanged.push(c.name);
    }
    for (const name of managedByName.keys()) if (!seen.has(name)) report.removed.push(name);
    if (!KEEP_DEFAULTS) for (const app of findWizardApps()) report.pruned.push(app.name);
    if (pruneWidgets)
      for (const w of findWizardWidgets()) report.pruned.push("widget: " + w.kind);
  } else {
    sync();
    if (pruneWidgets) fs.writeFileSync(WIZARD_WIDGET_FLAG, new Date().toISOString() + "\n");
  }
  db.close();

  console.log((DRY_RUN ? "[DRY RUN] " : "") + "Board: " + board.name);
  for (const k of ["added", "removed", "pruned", "updated"])
    for (const n of report[k]) console.log("  " + k + ": " + n);
  console.log(
    "  summary: " +
      report.added.length + " added, " +
      report.removed.length + " removed, " +
      report.pruned.length + " pruned, " +
      report.updated.length + " updated, " +
      report.unchanged.length + " unchanged"
  );
  return report.added.length + report.removed.length + report.pruned.length + report.updated.length;
}

scanContainers()
  .then((containers) => {
    const changes = main(containers);
    process.exit(changes > 0 ? 0 : 0);
  })
  .catch((err) => {
    console.error("ERROR: " + err.message);
    process.exit(1);
  });
