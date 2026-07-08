# flashforge (FlashForgeAdventurer5MAPI)

Web API + simple GUI to monitor a FlashForge Adventurer 5M (Pro) 3D printer, from [IgorZyktin/FlashForgeAdventurer5MAPI](https://github.com/IgorZyktin/FlashForgeAdventurer5MAPI). Uses the printer's built-in network API — no printer/firmware modification needed. Port **9876**.

The container itself is stateless and printer-agnostic: the printer IP is part of every URL, not container config.

## Install

```bash
bash install.sh
```

- Prompts for the **printer IP** (default `192.168.1.113`); non-interactive installs use `PRINTER_IP=<ip> bash install.sh`. Re-runs default to the previously saved value.
- Prompts for an optional **camera stream URL** (see [Camera feed](#camera-feed) below); non-interactive: `CAMERA_URL=<url>`.
- Both values are saved to `.env`; the printer IP is also attached to the container as the docker label `flashforge.printer_ip`.
- `install.sh` clones the upstream repo (the Dockerfile copies its `adventurer5m/` Flask app into the image) and runs `docker compose up -d --build`. Re-run to update to the latest upstream source.

## Use

- GUI: `http://<docker-host>:9876/en/<printer-ip>` (also `/ru/<printer-ip>`)
- API: `curl http://<docker-host>:9876/api/execute/<printer-ip>/progress` (also `temperature`, `position`, `info`, `status`)

## Camera feed

The GUI's "video from the printer" section is an `<img>` pointing at the printer's own MJPEG camera stream, `http://<printer-ip>:8080/?action=stream`. Only the Adventurer 5M **Pro** (or a 5M with the camera accessory, enabled on the touchscreen under Settings → Camera) serves that stream — on a plain 5M the section stays blank.

`install.sh` therefore asks for an optional **camera stream URL**. If given, the upstream GUI templates are patched before the build so the section shows that stream instead. Rules:

- Must be an **MJPEG stream or plain image URL** — it lands in an `<img>` tag, so RTSP/HLS won't work.
- Must be reachable **from the browser** (the img is loaded client-side), without authentication headers.
- Empty answer keeps the previous value (or the printer default); answer `-` to clear a saved URL and go back to the printer camera.

Example — a motionEye camera streams at `http://<motioneye-host>:<stream-port>/` (per-camera "Streaming Port" in motionEye's Video Streaming settings, e.g. `http://192.168.1.37:9081/`).

Changing the URL later: re-run `install.sh` (it re-clones upstream and re-patches, then rebuilds).

## homarr integration

`homarr/findtargetcontainers.sh` has a built-in special case for the container name `FlashForgeAdventurer5MAPI`: the tile URL is built as `http://<docker-host>:9876/en/<printer-ip>`, with the printer IP read from the `flashforge.printer_ip` label (set at install time). Change the printer IP by re-running `install.sh`, then re-run the homarr sync.
