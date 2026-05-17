---
title: Raspberry Pi 4 (headless)
---

# Running PushNav headless on a Raspberry Pi 4

PushNav runs headless on a Raspberry Pi 4 (Debian 13 / aarch64) and is
controlled entirely from a phone on the same Wi-Fi via the existing
mobile web UI at `http://<pi-ip>:8765`. This page is the install-and-run
runbook; the laptop builds (macOS `.app`, Windows installer, Linux
x86_64 AppImage) are unchanged.

!!! note "Scope"
    This is "make it work from source" — no auto-start, no mDNS, no
    pre-flashed SD-card image. Those land in a later appliance milestone.

## Prerequisites

- Raspberry Pi 4 (4 GB or more) running Raspberry Pi OS / Debian 13.
- An [openaicam USB camera](hardware.md) (VID `0x32E6` / PID `0x9251`) —
  the Linux camera server targets this device specifically.
- A phone on the same Wi-Fi as the Pi for the UI.

System packages and `uv`:

```bash
sudo apt update
sudo apt install -y gcc libjpeg-dev nodejs npm
# Add your user to the `video` group so the camera server can open
# /dev/video0 without sudo; log out and back in afterwards.
sudo usermod -aG video "$USER"
# Install uv per https://docs.astral.sh/uv/getting-started/installation/
```

## Clone and build

```bash
git clone git@github.com:meridianfield/pushnav.git
cd pushnav
uv sync
make -C camera/linux
(cd web && npm install && npm run build)
```

`uv sync` fetches a standalone Python 3.12 (one-time, ~30 MB) and
installs the Python deps. `make` produces `camera/linux/camera_server`.
`npm run build` writes the React UI to `web/dist/`.

## Run

```bash
uv run python -m evf.main --no-window
```

Expected first-startup log lines (in any order):

- `Spawned camera server (PID ...)`
- `Camera HELLO` (handshake complete)
- `Stellarium server listening on 127.0.0.1:10001`
- `LX200 server listening on 0.0.0.0:4030`
- `Mobile web interface at http://<pi-ip>:8765`

Press Ctrl-C to stop. The engine cleans up all subsystems before
exiting.

!!! tip "Keep it running after SSH disconnect"
    If you started the engine over SSH and want it to survive when
    you log out, run it under `tmux` (or `nohup`):

    ```bash
    tmux new -s pushnav
    # inside tmux:
    uv run python -m evf.main --no-window
    # Ctrl-b d to detach; the engine keeps running.
    # tmux attach -t pushnav  to reattach later.
    ```

    Or, without tmux:

    ```bash
    nohup uv run python -m evf.main --no-window > pushnav.log 2>&1 &
    disown
    # tail -f pushnav.log  to watch startup.
    ```

## Connect from a phone

1. Find the Pi's LAN IP: `ip -4 -o addr show scope global`.
2. On a phone joined to the same Wi-Fi, open
   `http://<pi-ip>:8765`. The Navigation tab is the default.
3. Optional — connect SkySafari or Stellarium Mobile to the LX200
   server at `<pi-ip>:4030` (Meade LX200 Classic, TCP).

## Troubleshooting

**`Camera server not listening on 127.0.0.1:8764`** — Either the
openaicam isn't plugged in (`lsusb | grep 32e6:9251`) or your user
isn't in the `video` group (`groups | grep video`).

**`Permission denied: /dev/video0`** — As above; `sudo usermod -aG
video "$USER"` and log out / back in.

**`Port 8765 is in use`** — Another PushNav (or something else) is
already on that port. Find it with `lsof -i :8765` and stop it, or
change `webserver.port` in your config file
(`~/.config/electronic-viewfinder/config.json` on Linux).

**Phone can't reach the URL** — Confirm phone and Pi are on the same
Wi-Fi SSID (not Pi on Ethernet + phone on Wi-Fi unless your router
routes between them). Some captive-portal Wi-Fi APs block client-to-
client traffic; try a regular home network.

**Audio warnings in the log** — Harmless on a headless Pi with no
audio sink. The engine plays lock/lost/goto_ack WAVs through
`playsound3`; if there's no sink it logs once and continues.

**Slow first plate-solve** — tetra3 loads the ~85 MB star database
into memory on first call; subsequent solves are fast. The Pi 4 itself
is several times slower than an x86 laptop at tetra3's matmul, so
individual frame solves take 1–6 seconds depending on the sky region
(vs <100 ms on a laptop). The solver timeout is platform-tuned so
valid solves complete; you may just see longer between locks than on
a laptop.

## Limitations

- No auto-start. You run `uv run python -m evf.main --no-window`
  manually after each boot.
- No mDNS / `pushnav.local`. Type the IP into the phone.
- No Wi-Fi onboarding. Configure the Pi's Wi-Fi the usual way
  (Raspberry Pi Imager, `raspi-config`, or `nmcli`).
- No in-app settings UI. The desktop app exposes settings through a
  Settings panel; on headless there is no window, so tweaks
  (`webserver.port`, audio, etc.) go through
  `~/.config/electronic-viewfinder/config.json` directly. Restart the
  engine after editing.

Each of these is on the roadmap as a later appliance slice.
