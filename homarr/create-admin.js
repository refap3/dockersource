// create-admin.js — executed INSIDE the homarr container by install.sh
// (docker exec ... node < create-admin.js).
//
// Creates the initial admin user directly in the DB and marks onboarding as
// finished, so the web wizard never runs (a stale browser tab can silently
// break it — see README). Mirrors exactly what the wizard's user step writes:
// user row (bcrypt password), credentials-admin group with admin permission,
// membership in the everyone group.
//
// Environment (set by install.sh):
//   ADMIN_USER      username (required)
//   ADMIN_PASSWORD  password (required)
//
// No-op if any user already exists.

const bcrypt = require("bcrypt");
const db = require("better-sqlite3")("/appdata/db/db.sqlite");

const username = process.env.ADMIN_USER;
const password = process.env.ADMIN_PASSWORD;
if (!username || !password) {
  console.error("ERROR: ADMIN_USER / ADMIN_PASSWORD not set");
  process.exit(1);
}

// cuid2-style id like homarr generates: lowercase letter + 23 [a-z0-9]
function newId() {
  const alpha = "abcdefghijklmnopqrstuvwxyz";
  const alnum = alpha + "0123456789";
  let id = alpha[Math.floor(Math.random() * 26)];
  for (let i = 0; i < 23; i++) id += alnum[Math.floor(Math.random() * 36)];
  return id;
}

if (db.prepare("SELECT count(*) AS c FROM user").get().c > 0) {
  console.log("A user already exists — skipping admin creation.");
  process.exit(0);
}

db.transaction(() => {
  const userId = newId();
  db.prepare(
    "INSERT INTO user (id, name, password, provider) VALUES (?, ?, ?, 'credentials')"
  ).run(userId, username, bcrypt.hashSync(password, 10));

  // "everyone" group: normally created by the wizard; home board = default board
  const board = db.prepare("SELECT id FROM board ORDER BY name = 'dashboard' DESC LIMIT 1").get();
  let everyone = db.prepare('SELECT id FROM "group" WHERE name = ?').get("everyone");
  if (!everyone) {
    everyone = { id: newId() };
    db.prepare('INSERT INTO "group" (id, name, position, home_board_id) VALUES (?, ?, -1, ?)').run(
      everyone.id,
      "everyone",
      board ? board.id : null
    );
  }

  // admin group owned by the new user, like the wizard creates it
  const adminGroupId = newId();
  db.prepare('INSERT INTO "group" (id, name, owner_id, position) VALUES (?, ?, ?, 0)').run(
    adminGroupId,
    "credentials-admin",
    userId
  );
  db.prepare("INSERT INTO groupPermission (group_id, permission) VALUES (?, 'admin')").run(adminGroupId);
  db.prepare("INSERT INTO groupMember (group_id, user_id) VALUES (?, ?)").run(adminGroupId, userId);
  db.prepare("INSERT INTO groupMember (group_id, user_id) VALUES (?, ?)").run(everyone.id, userId);

  const ob = db.prepare("SELECT id FROM onboarding LIMIT 1").get();
  if (ob) db.prepare("UPDATE onboarding SET step = 'finish', previous_step = NULL WHERE id = ?").run(ob.id);
  else db.prepare("INSERT INTO onboarding (id, step, previous_step) VALUES (?, 'finish', NULL)").run(newId());
})();

console.log("Admin user '" + username + "' created; onboarding marked finished.");
