# TEMPORARY handoff note: `feat/pushnav-headless-deb`

> **Delete this file before merging.** It exists only to carry context
> between the Raspberry Pi 5 dev box and the Linux PC.

Written 2026-10-06 on the Pi; updated the same day on the Linux PC with
the results of the checks below. Plan with per-task details and results:
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

## Verified on the Linux PC (x86_64), 2026-10-06

### 1. Full CI run: passed

[Run 37435807221](https://github.com/meridianfield/pushnav/actions/runs/37435807221)
(`platform=all`, `create_release=false`): `build-macos`, `build-linux`,
`build-windows` (36 min) and `build-headless-deb` all succeeded;
`release` was skipped.

- **pywebview:** the plain `uv sync` in CI installed `pywebview==6.2.1` in
  the macOS, Linux and Windows jobs, so `default-groups` works with the
  uv version in CI.
- **scipy:** Nuitka didn't pull it in. The only "scipy" in the logs is
  `numpy.libs/libscipy_openblas64_…dll`, which is numpy's own OpenBLAS.
- Warnings only: Nuitka's usual numpy `doctest` anti-bloat warning, and
  GitHub's Node.js 20 deprecation notice for `actions/checkout@v4` and
  `actions/upload-artifact@v4`.
- `gh` on the Linux PC must be logged in as `arunvenkataswamy` (admin).
  `arun-venkataswamy` only has read access and gets HTTP 403 on
  `gh workflow run`.

### 2. Desktop app: command-line checks passed

- `uv sync` removed scipy and qrcode; `import webview` and
  `import PyQt6` work; `import scipy` gives `ModuleNotFoundError`.
- `uv run pytest tests/`: 295 passed.
- `make -C camera/linux` (already up to date) and `npm run build` succeed.
- `git grep -i scipy` finds nothing outside this note, `uv.lock` and the
  plan.

### scipy → numpy rotation: re-checked on x86

Compared the current `solver/sync.py` with the pre-`65ccf7d` scipy
version (`uv run --with scipy`, scipy 1.18.1, numpy 2.4.2), using
`compute_body_frame_sync` + `apply_body_frame_sync`:

| Cases | Max difference |
|---|---|
| 100k random sync/track pairs, sync star up to 30° off-axis, roll −360..720 | 3.6e-9 arcsec on sky; 6.7e-16 in `d_body` |
| 5,625 pairs at/near the poles, RA 0/360, roll wraparound | 3.1e-3 arcsec |
| Orientation matrix `T` | `|TᵀT − I|` ≤ 5.6e-16, `det(T)` = 1 |

The 3 milliarcsec at the poles isn't from the rotation code. In the worst
case the two outputs differ by one ULP in the z component at Dec ≈ +90°,
and `vec_to_radec`'s `arcsin(z)` turns that into exactly
√(2·1.1e-16) rad = 3.07 mas. The scipy version has the same limit.

Gap (not addressed): `tests/test_sync.py` computes its expected values
with the same `orientation_from_radec_roll` it tests, so nothing in the
repo independently checks the rotation, and the scipy comparison was
never committed. A possible follow-up: golden input/output values
captured from the scipy version, plus an orthonormality/det check over
random RA/Dec/roll. Not done yet; waiting on a decision.

## Still to do

### Desktop window checks (needs a person at the Linux PC)

```bash
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

### Optional

- Build the Linux release locally: `scripts/build_linux.sh` (CI already
  built it).
- The .deb build on x86: `scripts/build_headless_deb.sh` runs the arm64
  container under QEMU. It's slow, but it confirms the "build on a PC"
  path from the plan. It needs `qemu-user-static` and `binfmt-support`.

## After that

- Delete this file (`git rm TEMP-HANDOFF-pushnav-headless.md`), commit,
  push.
- Open the PR to `main`.
- Decided not to do: give `SubprocessManager`'s recovery loop the USB
  check. Its retries after an unplug stay noisy in the log; that's
  intentional for now.
- Still open from earlier: GitHub reports 109 Dependabot alerts on `main`
  (38 high). They aren't from this branch.
