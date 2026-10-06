# pushnav-headless apt Package Implementation Plan

> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship PushNav for Raspberry Pi as an apt-installable `.deb`
named `pushnav-headless`. A regular Pi user runs
`sudo apt install ./pushnav-headless_<ver>_arm64.deb`, plugs in the
camera, and opens `http://<pi-ip>:8765` on a phone. No `uv`, `npm`,
`make`, or git on the Pi.

**Naming:** the `-headless` suffix keeps this distinct from the regular
Linux PC/laptop build (Nuitka tar.gz / AppImage). Pi builds are
*always* headless — there is no desktop window variant.

| Thing | Name |
|---|---|
| apt package | `pushnav-headless` (arm64 only) |
| Command | `/usr/bin/pushnav-headless` (always `--no-window`) |
| systemd unit | `pushnav-headless.service` (enabled + started on install) |
| System user | `pushnav` (member of `video`) |
| Debian version | `0.3.0~beta-1` (`~` sorts before the final `0.3.0`) |

**Decisions (2026-10-06):**
1. Bundle a standalone Python 3.12 (python-build-standalone, same
   interpreter `uv` uses) so one `.deb` works on Pi OS bookworm
   (system Python 3.11, unsupported) and trixie (3.13).
2. The service is enabled and started on install.
3. The engine keeps retrying the camera in the background when headless,
   so the phone UI is reachable before the camera is plugged in and
   recovers by itself after a disconnect.

**Out of scope:** hosted/signed apt repository (GitHub Releases first),
appliance features (hotspot, read-only root, shutdown button, clock
from phone), SD-card image.

**Branch:** `feat/pushnav-headless-deb`

---

## Findings that shape the plan

- `main.py` already imports `webview` lazily, only on the window path,
  so headless never touches it. The work is to stop *installing* it.
- `qrcode[pil]` is not imported by any Python code — the Settings QR is
  rendered by `qrcode.react` in the web UI.
- `paths.py` already has a Linux release layout (`_LINUX_RELEASE`:
  `camera_server` + `data/` + `marketing/` next to the executable). The
  package reuses that layout under `/usr/lib/pushnav-headless/`.
- Config and log dirs come from `XDG_CONFIG_HOME` / `XDG_STATE_HOME`,
  so the unit can point them at `/var/lib/pushnav-headless` with no
  code change.
- `/dev/video*` is `root:video 0660`; a system user in `video` is
  enough — no udev rule. The camera server's allowlist covers the
  Waveshare, Arducam and DECXIN OV9281 modules.
- **Camera gap:** `Engine.startup_camera()` runs once. If no camera is
  attached it logs an error and nothing retries. `SubprocessManager`'s
  recovery loop only runs after a successful connection drops, and
  gives up (`EngineState.ERROR`) after 5 attempts. `Engine.retry_camera()`
  exists but is only called from the UI's "Retry camera" button
  (`POST /api/camera/retry`).
- The release `camera_server` must be compiled against an old enough
  glibc: a binary built on Ubuntu 24.04 or trixie will not run on
  bookworm (glibc 2.36). Python wheels are `manylinux_2_28`, fine on
  both.

---

### Task 1: Make the desktop window dependencies optional

**Files:** `pyproject.toml`, `uv.lock`

- [ ] Move `pywebview>=5.0` and `pywebview[qt]>=5.0 ; sys_platform == 'linux'`
      (with their explanatory comment) into a new `[dependency-groups] desktop`.
- [ ] Add `[tool.uv] default-groups = ["dev", "desktop"]` so plain
      `uv sync` is unchanged for development and for the macOS / Windows /
      Linux-laptop build scripts and CI.
- [ ] Remove the unused `qrcode[pil]` dependency (Pillow stays — the
      solver uses it).
- [ ] `uv lock`; verify `uv sync` still installs pywebview and
      `uv sync --no-group desktop` does not.
- [ ] Run `uv run pytest tests/` — must pass.
- [ ] Confirm `uv run python -m evf.main --no-window` starts in a venv
      without the desktop group.

### Task 2: Background camera retry when headless

**Files:** `python/evf/engine/engine.py`, `python/evf/main.py`, `tests/`

- [ ] Add a lock around `Engine.retry_camera()` so the UI button and the
      background retry can't spawn two camera servers at once.
- [ ] Add `Engine.start_camera_watchdog(interval_s=10)`: a daemon thread
      that, every interval, calls `retry_camera()` when
      `camera_connected` is False **and** the `SubprocessManager` is not
      mid-recovery (don't stomp on its own backoff loop). Stops on
      `engine.shutdown()`.
- [ ] Rate-limit logging: one "Waiting for camera…" line when the camera
      first goes missing, one "Camera connected" on success — not an
      error line every 10 s.
- [ ] Ensure a successful retry from `EngineState.ERROR` returns the
      state machine to `SETUP` (same as recovery does).
- [ ] Call it from `main.py` only on the `--no-window` path. The desktop
      app keeps its current behaviour (Retry button).
- [ ] Unit test with a fake `SubprocessManager`: watchdog retries while
      disconnected, stops retrying once connected, skips while recovering,
      exits on shutdown.
- [ ] Manual on this Pi: start with camera unplugged → web UI reachable;
      plug in → connects within ~10 s; unplug/replug → recovers.

### Task 3: Headless install-root detection in `paths.py`

**Files:** `python/evf/paths.py`, `tests/`

- [ ] Treat `PUSHNAV_ROOT=<dir>` (set by the launcher) as a Linux
      release root, reusing every existing `_LINUX_RELEASE` branch
      (`camera_server`, `data/tetra3rs_gaia.bin`, `data/VERSION.json`,
      `data/sounds`, `data/web_dist`, `data/samples`, `marketing/`).
- [ ] Test: with `PUSHNAV_ROOT` pointing at a temp dir in release
      layout, all path functions resolve inside it.

### Task 4: Package layout, launcher and maintainer scripts

**Files (new):** `packaging/headless/` — `pushnav-headless` (launcher),
`pushnav-headless.service`, `debian/control.in`, `debian/postinst`,
`debian/prerm`, `debian/postrm`

Installed layout:
```
/usr/lib/pushnav-headless/
  python/            standalone CPython 3.12 + site-packages (evf + deps)
  camera_server
  data/              tetra3rs_gaia.bin, VERSION.json, sounds/, web_dist/, samples/
  marketing/
/usr/bin/pushnav-headless
/lib/systemd/system/pushnav-headless.service
```

- [ ] Launcher: `exec env PUSHNAV_ROOT=/usr/lib/pushnav-headless
      /usr/lib/pushnav-headless/python/bin/python3 -m evf.main --no-window "$@"`.
- [ ] Unit: `User=pushnav`, `SupplementaryGroups=video`,
      `StateDirectory=pushnav-headless`,
      `Environment=XDG_CONFIG_HOME=/var/lib/pushnav-headless/config`
      and `XDG_STATE_HOME=/var/lib/pushnav-headless/state`,
      `Restart=on-failure`, `RestartSec=5`, `After=network-online.target`,
      `WantedBy=multi-user.target`. SIGTERM already triggers a clean
      `engine.shutdown()`.
- [ ] `control`: `Package: pushnav-headless`, `Architecture: arm64`,
      `Depends: libjpeg62-turbo, adduser`, `Section: science`,
      description making clear it's the headless Raspberry Pi build.
- [ ] `postinst`: create system user `pushnav` (no login, home
      `/var/lib/pushnav-headless`), add to `video`, `systemctl enable --now`.
      Print the phone URL (LAN IP + `:8765`).
- [ ] `prerm`: stop the service. `postrm purge`: disable, remove the
      user and `/var/lib/pushnav-headless`.
- [ ] Running `pushnav-headless` by hand while the service is up hits the
      existing single-instance guard — make sure its message mentions
      `sudo systemctl stop pushnav-headless`.

### Task 5: Build script

**Files (new):** `scripts/build_headless_deb.sh`

- [ ] Runs inside a `debian:bookworm` arm64 container (native on a Pi or
      ARM CI runner; QEMU on an x86 PC). Flag to run directly on the
      host for quick iteration.
- [ ] Steps: build `camera/linux/camera_server` (gcc + libjpeg-dev) →
      build the React UI (`npm ci && npm run build`) → fetch
      python-build-standalone 3.12 via `uv python install` and copy it
      into the staging tree → install deps from
      `uv export --frozen --no-dev --no-group desktop` plus the `evf`
      package into that interpreter → copy `data/` and `marketing/` →
      strip `__pycache__`, tests, and the `gaia-catalog` blob only if it
      is truly unused at runtime (verify first) → `dpkg-deb --build
      --root-owner-group`.
- [ ] Version from `data/VERSION.json` (`0.3.0-beta` → `0.3.0~beta-1`).
- [ ] Output: `build/pushnav-headless_<ver>_arm64.deb`. Report its size.

### Task 6: CI

**Files:** `.github/workflows/build.yml`

- [ ] New job `build-headless-deb` on `ubuntu-24.04-arm`, running
      `scripts/build_headless_deb.sh` in `debian:bookworm`.
- [ ] Smoke test in a fresh `debian:bookworm` and `debian:trixie`
      container: `apt install ./*.deb`, run `pushnav-headless` with no
      camera for a few seconds, assert `GET /api/version` returns
      `"app": "pushnav"`.
- [ ] Add a `headless` option to the `platform` input; add the job to
      `release.needs` and upload the `.deb` as a release asset.

### Task 7: Docs

**Files:** `docs/rpi-headless.md`, `README.md`, `docs/install.md`,
`CLAUDE.md`

- [ ] Rewrite `docs/rpi-headless.md`: apt install as the primary path
      (download `.deb`, `sudo apt install ./…`, open URL), service
      management (`systemctl status/stop/disable`, `journalctl -u`),
      config location (`/var/lib/pushnav-headless/config/…`), Pi 4 and
      Pi 5 both supported. Keep from-source as a developer section and
      fix its Stellarium log line (`0.0.0.0:10001`).
- [ ] Mention the `pushnav-headless` package in install docs and README.
- [ ] Note the `desktop` dependency group and the new build script in
      `CLAUDE.md`.

### Task 8: Hardware verification (this Pi 5, trixie)

- [ ] Fresh install of the built `.deb`; service active; phone UI works;
      camera streams.
- [ ] Reboot → comes back by itself.
- [ ] Boot with camera unplugged → UI reachable; plug in → connects.
- [ ] Unplug / replug during use → recovers.
- [ ] Reinstall / upgrade over an older version keeps config.
- [ ] `apt purge` removes user, state and unit.
- [ ] Record the installed size and first-solve time on Pi 5.
