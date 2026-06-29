# Raspberry Pi 4 headless mode — design

**Date:** 2026-05-17
**Status:** Approved for implementation planning
**Branch:** `rpi-appliance`

## Goal

Run PushNav headless on a Raspberry Pi 4 (Debian 13 / aarch64) and drive it
entirely from a phone on the same Wi-Fi via the existing mobile web UI at
`http://<pi-ip>:8765`. No window, no auto-start, no provisioning UX —
this slice is the smallest possible "does it work?" pass on a Pi, ahead
of any later appliance polish.

The existing laptop builds (macOS .app, Windows installer, Linux x86_64
AppImage) must continue to work unchanged. All new aarch64 / headless
changes are additive.

## Scope

### In scope

- Build the C/V4L2 camera server on the Pi (`make -C camera/linux`).
- Build the React UI (`npm install && npm run build`).
- `uv sync` of Python deps using uv-managed Python 3.12 on aarch64.
- Run `uv run python -m evf.main --no-window` and verify all four
  subsystems come up: Stellarium (`localhost:10001`), LX200
  (`0.0.0.0:4030`), webserver (`0.0.0.0:8765`), camera subprocess on
  `127.0.0.1:8764`.
- Smoke-test from a phone: open the mobile web UI, see the MJPEG frame,
  run the sync wizard against real sky, GOTO a buddy-catalog target,
  and confirm the LX200 server drives SkySafari **or** Stellarium
  Mobile.
- Capture aarch64-specific fixes (build flags, missing system packages,
  device permissions) as small commits on the `rpi-appliance` branch.
- A short runbook covering install, run, and the troubleshooting
  surface listed under "Known risks" below.

### Out of scope (deferred to later "appliance" slices)

- systemd unit / auto-start on boot.
- mDNS (`pushnav.local`) advertising or a console startup banner.
- Wi-Fi onboarding, hotspot fallback, captive portal.
- Pre-flashed SD-card image (`pi-gen` or similar).
- Dependency slimming (dropping `pywebview[qt]` on headless installs).
- Appliance-only UI changes (shutdown/reboot buttons, Wi-Fi switcher).
- Nuitka-built AppImage on aarch64 — covered by `build_linux.sh` and
  worth verifying separately, but not part of this slice.

## What's already in place

Audit of the current tree (see `python/evf/main.py`,
`python/evf/webserver/server.py`, `python/evf/network.py`,
`python/evf/paths.py`, `python/evf/camera/subprocess_mgr.py`,
`camera/linux/camera_server.c`, `scripts/build_linux.sh`):

- `main.py` already supports `--no-window`: spins up engine + all three
  TCP servers + camera subprocess, then `Event.wait()`s on
  `SIGINT`/`SIGTERM`. No code changes required to run headless.
- The aiohttp webserver binds `0.0.0.0:8765`, serves the React build,
  exposes `/frame.mjpg`, `/ws`, and the full `/api/*` surface — the
  mobile web UI is the canonical UI when no window is open.
- The LX200 server binds `0.0.0.0:4030` so phone apps on the same LAN
  reach it directly.
- `evf.network.local_ip()` already picks up the LAN-routable interface
  for the URL the web client shows.
- `paths.py` already handles a Linux release layout (`_LINUX_RELEASE`)
  in addition to dev mode; nothing platform-specific to add for the Pi
  in source-install mode.
- The C/V4L2 camera server already targets the openaicam (VID 0x32E6 /
  PID 0x9251) — the same camera enumerated on this Pi.

## Approach

**Source-install via uv on this Pi.** Identical to dev workflow on
Linux, minus Vite:

```bash
# Prereqs (one-time)
sudo apt install gcc libjpeg-dev nodejs npm   # if not already present
# Confirm membership in the `video` group: `groups | grep video`

# Build + run
uv sync
make -C camera/linux
(cd web && npm install && npm run build)
uv run python -m evf.main --no-window
```

Engine logs print the LAN URL. Phone joins the same Wi-Fi, opens
`http://<pi-ip>:8765`.

We considered building the existing `build_linux.sh` AppImage on the Pi
and running it with `--no-window`. Deferred: Nuitka compile on a Pi 4
is slow (~30 min+), and any failure mode is harder to diagnose than a
source-install. Once the source path is known-good we may revisit the
AppImage build as a follow-up.

## Known risks (where surprises are likely)

These are the spots most likely to need a small fix. Each one gets
investigated in order during the smoke test; fixes land as small
commits on `rpi-appliance`.

1. **`pywebview[qt]` on aarch64.** `pyproject.toml` pulls
   `pywebview[qt]>=5.0 ; sys_platform == 'linux'`, which brings PyQt6
   + PyQt6-WebEngine (~200 MB). Wheels exist for `linux_aarch64` from
   Qt 6.5+ — likely installs cleanly. If it fails, the fix path is a
   future `[project.optional-dependencies]` group, not in scope here.
2. **`playsound3` on a headless Pi.** Debian trixie ships PipeWire and
   the engine plays `lock`/`lost`/`goto_ack` WAVs. If no audio sink is
   available the engine should log a warning and continue. Verify
   warnings don't promote to fatal errors.
3. **`/dev/video0` access.** The C camera server opens the V4L2 device.
   User must be in the `video` group; otherwise the server exits and
   `SubprocessManager`'s backoff loop will keep retrying. Pre-flight:
   `groups | grep video`.
4. **System build deps.** `gcc` + `libjpeg-dev` for the camera server;
   `nodejs` + `npm` for the React build. Apt one-liner if missing.
5. **Port conflicts.** 8765 / 4030 / 10001 / 8764 — pre-flight that
   nothing else is squatting on them.
6. **uv-managed Python 3.12 on aarch64.** System Python is 3.13.5; uv
   should fetch a 3.12 standalone build from python-build-standalone
   (which has `aarch64-unknown-linux-gnu` artifacts). Expected to be
   transparent.

## Verification plan

1. **Engine startup.** `uv run python -m evf.main --no-window` prints:
   - tetra3 database loaded
   - Stellarium server bound to `localhost:10001`
   - LX200 server bound to `0.0.0.0:4030`
   - Webserver listening on port 8765 + LAN URL log line
   - Camera HELLO received with `1280x720` MJPEG frames flowing
2. **Phone web UI.** Open `http://<pi-ip>:8765` on a phone joined to
   the same Wi-Fi:
   - Live MJPEG renders in the Navigation tab.
   - WebSocket state updates (state pill changes, frame timestamps
     advance).
   - Sync wizard runs end-to-end against real sky.
   - Select a buddy-catalog target → arrow + push-to overlay appear.
3. **LX200 client.** With SkySafari or Stellarium Mobile (your pick):
   connect telescope as Meade LX200 Classic at `<pi-ip>:4030`, slew
   to a known target, confirm the GOTO request reaches the engine and
   the push-to arrow tracks toward it.

The verification pass is the implementation. Anything that fails along
the way becomes a small fix and a line in the runbook.

## Deliverables

- Zero or more small commits on `rpi-appliance` for aarch64 fixes
  uncovered during verification.
- A runbook — likely a new `docs/rpi-headless.md` linked from the
  install or hardware docs — covering: prereqs, the four build
  commands above, expected log lines, and the troubleshooting list
  from "Known risks".
- This design doc, committed to the same branch.

## Backwards compatibility

Every change is additive:

- No edits to `main.py` startup logic — `--no-window` is the existing
  contract.
- No new dependencies in `pyproject.toml`.
- The runbook is a new doc file.
- Any aarch64 fixes (e.g., a `Makefile` tweak, a missing import guard)
  apply universally; they don't change behaviour on x86_64 or other
  platforms.

The existing macOS `.app`, Windows installer, and Linux x86_64
AppImage / tar.gz builds keep producing identical artifacts.
