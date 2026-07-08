# flashforge (FlashForgeAdventurer5MAPI)

Web API + simple GUI to monitor a FlashForge Adventurer 5M (Pro) 3D printer, from [IgorZyktin/FlashForgeAdventurer5MAPI](https://github.com/IgorZyktin/FlashForgeAdventurer5MAPI). Uses the printer's built-in network API — no printer/firmware modification needed. Port **9876**.

The container itself is stateless and printer-agnostic: the printer IP is part of every URL, not container config.

## Install

```bash
bash install.sh
```

- Prompts for the **printer IP** (default `192.168.1.113`); non-interactive installs use `PRINTER_IP=<ip> bash install.sh`. Re-runs default to the previously saved value.
- The IP is saved to `.env` and attached to the container as the docker label `flashforge.printer_ip`.
- `install.sh` clones the upstream repo (the Dockerfile copies its `adventurer5m/` Flask app into the image) and runs `docker compose up -d --build`. Re-run to update to the latest upstream source.

## Use

- GUI: `http://<docker-host>:9876/en/<printer-ip>` (also `/ru/<printer-ip>`)
- API: `curl http://<docker-host>:9876/api/execute/<printer-ip>/progress` (also `temperature`, `position`, `info`, `status`)

## homarr integration

`homarr/findtargetcontainers.sh` has a built-in special case for the container name `FlashForgeAdventurer5MAPI`: the tile URL is built as `http://<docker-host>:9876/en/<printer-ip>`, with the printer IP read from the `flashforge.printer_ip` label (set at install time). Change the printer IP by re-running `install.sh`, then re-run the homarr sync.
