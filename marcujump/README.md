# marcujump

"Markus im Weltall" — a browser jump-and-run game (single-file HTML5 canvas), served by nginx.

The game source lives in its own repo: [refap3/marcujump](https://github.com/refap3/marcujump). The Docker image clones that repo at **build time**, so every build ships the current upstream version — nothing is vendored into this folder.

## Install

```bash
bash install.sh
```

Builds the image from the current upstream HEAD and starts the container. No configuration required.

- Game: `http://<host>:8093`
- Guide (Spielanleitung): `http://<host>:8093/MarcuJumpGuide.html`

## Update

```bash
bash update.sh
```

Fetches the upstream `index.html`, compares its SHA-256 hash with the copy inside the running container, and **only if it changed** rebuilds the image (with `--no-cache`) and restarts the container. If nothing changed upstream, it exits without touching the container. If the container isn't running, it builds and starts it.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Two-stage build: `git clone` upstream → copy `index.html` + `MarcuJumpGuide.html` into `nginx:alpine` |
| `docker-compose.yml` | Service definition, port 8093 → 80 |
| `install.sh` | Prerequisite check, build (cache-busted by upstream commit SHA), start |
| `update.sh` | Change detection + conditional rebuild (see above) |
