# TEMPORARY handoff note: `feat/pushnav-headless-deb`

> **Delete this file before merging.** It exists only to carry context from
> the Raspberry Pi 5 dev box to the Linux PC.

Written 2026-10-06. Plan with per-task details and results:
`docs/superpowers/plans/2026-10-06-pushnav-headless-deb.md`.

## What this branch does

Ships PushNav for Raspberry Pi as an apt package, **`pushnav-headless`**
(arm64, always headless; the `-headless` suffix keeps it distinct from the
Linux PC/laptop build). Users run
`sudo apt install ./pushnav-headless_<ver>_arm64.deb` and open
`http://<pi-ip>:8765` on a phone.

| Commit | Change |
|---|---|
| `3f25593` | `pywebview` + `pywebview[qt]` moved to a `desktop` dependency group, listed in `[tool.uv] default-groups`, so plain `uv sync` still installs them. Unused `qrcode[pil]` removed. |
| `dbf5ad7` | With `--no-window`, the engine runs a camera watchdog that retries the camera every 10 s. |
| `80c3a5e` | `PUSHNAV_ROOT` env var in `evf/paths.py` selects the Linux release layout. |
| `0337c2c`, `e6dd887` | `packaging/headless/` (launcher, systemd unit, maintainer scripts) + `scripts/build_headless_deb.sh`. |
| `65ccf7d` | **scipy removed.** `solver/sync.py` uses a plain numpy 3x3 rotation matrix. Matches scipy on 100k random cases (max 2.7e-9 arcsec). The `--include-package=scipy` lines were also removed from `build_mac.sh`, `build_linux.sh` and `build_windows.bat`. |
| `b76dc89` | Web server stop: cancel the serve task instead of `loop.stop()`. Fixes "Event loop stopped before Future completed" on every shutdown; websocket/MJPEG clients now get a proper close. |
| `076975f` | `startup_camera()` skips spawning `camera_server` when no USB video device is attached (Linux sysfs probe; always "present" on macOS/Windows). |
| `e0f2134` | CI: `build-headless-deb` job on `ubuntu-24.04-arm` + `scripts/smoke_test_headless_deb.sh`; the `.deb` is attached to releases. |
| `1dc1415` | Docs: `docs/rpi-headless.md` rewritten around apt install; install page, README, index, nav, CLAUDE.md updated. |

## Already verified (on the Pi 5)

- `uv run pytest tests/`: 295 passed.
- `.deb` installed on the Pi 5 (trixie): service starts at boot; booting
  without a camera logs one "Waiting for camera" line, and the camera
  connects by itself when plugged in; clean stop; `--reinstall` keeps
  config; `apt purge` removes everything.
- Container install smoke test passes on debian:bookworm and debian:trixie,
  locally and in CI
  ([run 37429677591](https://github.com/meridianfield/pushnav/actions/runs/37429677591)).
- `mkdocs build --strict` passes.

## NOT verified yet: do this on the Linux PC

The desktop builds were never run with this branch's dependency changes.
A full CI run was started and then cancelled (run 37430430167); only the
headless job finished.

### 1. Full CI run (no release)

```bash
gh workflow run build.yml --ref feat/pushnav-headless-deb -f platform=all -f create_release=false
gh run list --workflow build.yml --branch feat/pushnav-headless-deb --limit 1
gh run watch <run-id> --exit-status
```

Expect all four build jobs (`build-macos`, `build-linux`, `build-windows`,
`build-headless-deb`) to succeed; `release` is skipped.

Most likely failure points:

- **Nuitka builds.** scipy is gone from both the dependencies and the
  `--include-package` lists. If Nuitka still complains about scipy,
  something else imports it.
- **pywebview missing from a build.** CI runs a plain `uv sync`, which
  should install the `desktop` group through `default-groups`. If a build
  fails with `No module named 'webview'`, that mechanism isn't working
  with the uv version in CI.

### 2. Desktop app on the Linux PC (x86_64)

```bash
git fetch && git switch feat/pushnav-headless-deb
uv sync                                    # should still install pywebview + PyQt6
uv run python -c "import webview; print('webview ok')"
uv run python -c "import scipy" 2>&1 | tail -1   # expect ModuleNotFoundError
uv run pytest tests/
make -C camera/linux && (cd web && npm install && npm run build)
uv run python -m evf.main                  # window should open as before
```

In the window, check:

- The live view and Retry camera button work, with and without the camera
  plugged in. Without a camera, the log should show one
  "Waiting for camera" info line instead of camera_server errors.
- **Sync wizard end to end** (this exercises the numpy rotation code):
  solve, then confirm. Pointing after sync should match the target as
  before. `tests/samples` + `PUSHNAV_DEBUG=1` sample injection work if
  there's no sky.
- Closing the window: the log should have no "Web server error: Event loop
  stopped" line.

Optionally, build the Linux release locally: `scripts/build_linux.sh`.

### 3. Optional: the .deb build on x86

`scripts/build_headless_deb.sh` runs the arm64 container under QEMU on
x86. It's slow, but it confirms the "build on a PC" path from the plan.
It needs `qemu-user-static` and `binfmt-support`.

## After that

- Delete this file (`git rm TEMP-HANDOFF-pushnav-headless.md`), commit,
  push.
- Open the PR to `main`.
- Decided not to do: give `SubprocessManager`'s recovery loop the USB
  check. Its retries after an unplug stay noisy in the log; that's
  intentional for now.
- Still open from earlier: GitHub reports 109 Dependabot alerts on `main`
  (38 high). They aren't from this branch.
