# Raspberry Pi 4 Headless Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that the existing PushNav codebase runs headless on a Raspberry Pi 4 (Debian 13 / aarch64) under `--no-window`, with a phone on the same Wi-Fi as the sole UI. Capture any aarch64-specific fixes and a runbook so the next person can repeat the install in five minutes.

**Architecture:** Source-install via `uv` on the Pi (no Nuitka, no AppImage, no systemd, no mDNS). Build the C/V4L2 camera server and the React UI in place, run `uv run python -m evf.main --no-window`, drive everything from the phone web UI at `http://<pi-ip>:8765`. Each task is a verification step with concrete commands and expected output; commits land only when code or docs actually change.

**Tech Stack:**
- Python 3.12 (uv-managed via `python-build-standalone`) + aiohttp + tetra3 + numpy/scipy/Pillow
- React 18 + Vite + TypeScript (built once, served by aiohttp)
- C/V4L2 camera server (gcc + libjpeg) for the openaicam USB camera (VID 0x32E6 / PID 0x9251)
- Working branch: `rpi-appliance`
- Target host: this RPi 4 (Debian 13 trixie, kernel 6.18, aarch64)

**Spec:** `docs/superpowers/specs/2026-05-17-rpi-headless-design.md`

---

### Task 1: Pre-flight — system packages and device permissions

**Files:** None (system-level only).

This step verifies the Pi has the C toolchain, Node, libjpeg-dev, and that the running user can open `/dev/video*` without sudo. We do not install Python — `uv` will fetch its own standalone 3.12.

- [ ] **Step 1: Check apt packages**

Run:
```bash
dpkg -l gcc libjpeg-dev nodejs npm 2>&1 | grep -E '^ii|^dpkg-query: no packages' | awk '{print $2}'
```

Expected: four lines, each with `ii` on the left for `gcc`, `libjpeg-dev`, `nodejs`, `npm`.

If any are missing, install them:
```bash
sudo apt update
sudo apt install -y gcc libjpeg-dev nodejs npm
```

- [ ] **Step 2: Confirm `uv` is on PATH**

Run:
```bash
uv --version
```

Expected: `uv 0.x.y` printed; non-zero exit means uv is not installed. If missing, install per <https://docs.astral.sh/uv/getting-started/installation/> (single curl line) and re-shell.

- [ ] **Step 3: Confirm `/dev/video0` is accessible**

Run:
```bash
ls -l /dev/video0
groups | tr ' ' '\n' | grep -E '^video$' || echo "MISSING_VIDEO_GROUP"
```

Expected: `/dev/video0` shows group ownership `video` and your user is in the `video` group (the `grep` prints `video`, not `MISSING_VIDEO_GROUP`).

If the group is missing:
```bash
sudo usermod -aG video "$USER"
```
Then **log out and back in** so the new group sticks. The fix is permanent; re-run the group check before continuing.

- [ ] **Step 4: Confirm the target camera is connected**

Run:
```bash
lsusb | grep -i 32e6:9251 || echo "CAMERA_NOT_FOUND"
```

Expected: a line like `Bus 001 Device 003: ID 32e6:9251 openaicam openaicam`. If you see `CAMERA_NOT_FOUND`, plug in the openaicam before continuing. The engine still starts without a camera but the smoke tests below will be vacuous.

- [ ] **Step 5: Pre-flight the four ports**

Run:
```bash
ss -tln 'sport = :8765 or sport = :4030 or sport = :10001 or sport = :8764' | tail -n +2
```

Expected: no rows printed (all four ports free). If any are bound, stop the offending process before continuing — `lsof -i :<port>` to find the PID.

No commit (system-state only).

---

### Task 2: Build the C/V4L2 camera server

**Files:**
- Build target: `camera/linux/camera_server` (produced by `camera/linux/Makefile`)

- [ ] **Step 1: Clean and build**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
make -C camera/linux clean
make -C camera/linux
```

Expected: gcc compiles `camera_server.c` with no errors; the final line shows `gcc ... -o camera_server camera_server.c -ljpeg`.

- [ ] **Step 2: Verify the binary**

Run:
```bash
file camera/linux/camera_server
test -x camera/linux/camera_server && echo OK
```

Expected: `file` reports `ELF 64-bit LSB ... ARM aarch64`; `OK` printed.

- [ ] **Step 3: Quick standalone bind check (sanity, optional but cheap)**

Run:
```bash
./camera/linux/camera_server &
CAM_PID=$!
sleep 1
ss -tln 'sport = :8764' | tail -n +2
kill "$CAM_PID" 2>/dev/null
wait "$CAM_PID" 2>/dev/null
```

Expected: `ss` prints one row showing `LISTEN ... *:8764`. If it doesn't, the server failed to open the camera — check its stderr (rerun without `&` to see).

No commit (build artifact only; `camera/linux/camera_server` is gitignored).

---

### Task 3: `uv sync` — install Python deps including aarch64 wheels

**Files:**
- Touches: `.venv/` (created by uv)
- Reads: `pyproject.toml`, `uv.lock`

- [ ] **Step 1: Run `uv sync`**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
uv sync
```

Expected: uv downloads a standalone Python 3.12 (one-time, ~30 MB), then resolves and installs all deps including `pywebview[qt]` (PyQt6 + PyQt6-WebEngine, ~200 MB on linux_aarch64). Final line: `Installed N packages in X.YZs` with no errors.

**If `pywebview[qt]` fails to resolve a wheel for linux_aarch64:** this is the most likely aarch64-specific blocker. Do NOT mask it in this task — note the exact error message; the fix (an optional dep group keyed off platform) gets designed in Task 9 and lands as a separate commit. For now, you can unblock the rest of the plan with:
```bash
uv sync --no-install-package pywebview
```
This skips pywebview entirely; `--no-window` doesn't import it, so headless mode still works.

- [ ] **Step 2: Confirm Python and key packages are importable**

Run:
```bash
uv run python -c "import sys, tetra3, aiohttp, numpy, scipy, PIL, playsound3, erfa; print(sys.version)"
```

Expected: prints `3.12.x ...` on one line, no `ImportError`.

- [ ] **Step 3: Confirm the tetra3 star database file is present**

Run:
```bash
ls -lh data/hip8_database.npz
```

Expected: a file ~85 MB. If missing, that's a checkout-completeness issue (it's tracked in git LFS or directly — `git lfs pull` or `git checkout -- data/hip8_database.npz`).

No commit.

---

### Task 4: Build the React UI

**Files:**
- Touches: `web/node_modules/`, `web/dist/`
- Reads: `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/src/**`

- [ ] **Step 1: Install Node deps**

Run:
```bash
cd /home/arun/Devel/Github/pushnav/web
npm install
```

Expected: npm resolves and installs everything; ends with `added N packages` and zero `npm ERR!` lines. Vulnerabilities warnings are fine to ignore for this task.

- [ ] **Step 2: Production build**

Run:
```bash
cd /home/arun/Devel/Github/pushnav/web
npm run build
```

Expected: Vite prints `vite v... building for production...` and finally `✓ built in Xms`. No `Error:` lines.

- [ ] **Step 3: Verify the build output**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
test -f web/dist/index.html && echo OK
test -d web/dist/assets && ls web/dist/assets | head -5
```

Expected: `OK`; `assets/` contains hashed JS/CSS bundles.

No commit.

---

### Task 5: Headless engine smoke test

**Files:** None changed; this is a runtime verification.

- [ ] **Step 1: Start the engine in one terminal**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
uv run python -m evf.main --no-window 2>&1 | tee /tmp/pushnav.log
```

Expected within the first ~10 seconds, in any order:
- `Spawned camera server (PID ...): ...camera/linux/camera_server`
- A `Camera HELLO` or equivalent indicating the camera handshake completed
- `Stellarium server listening` on port 10001
- `LX200 server listening on 0.0.0.0:4030` (or equivalent — exact wording per `lx200/server.py`)
- `Mobile web interface at http://<pi-ip>:8765`
- `Web server listening on port 8765`

Leave this terminal running.

- [ ] **Step 2: Confirm all four ports are bound (from a second terminal)**

Open a second shell and run:
```bash
ss -tlnp 'sport = :8765 or sport = :4030 or sport = :10001 or sport = :8764' 2>/dev/null | tail -n +2
```

Expected: four `LISTEN` rows. 8765 and 4030 bind `0.0.0.0`; 10001 and 8764 bind `127.0.0.1`.

- [ ] **Step 3: Confirm the LAN URL works locally**

Run:
```bash
curl -sI "http://$(ip -4 -o addr show scope global | awk 'NR==1{print $4}' | cut -d/ -f1):8765/" | head -1
curl -s "http://127.0.0.1:8765/api/version"
```

Expected: first command prints `HTTP/1.1 200 OK`; second prints JSON like `{"app":"pushnav","version":"0.2.0","protocol_version":"..."}`.

- [ ] **Step 4: Clean shutdown**

In the engine terminal, press Ctrl-C once.

Expected: engine prints shutdown messages for each subsystem (camera, webserver, lx200, stellarium, solver) and the process exits with status 0. No hangs longer than ~5 seconds.

No commit.

---

### Task 6: Phone — mobile web UI smoke test

**Files:** None changed.

This step requires a phone on the same Wi-Fi as the Pi. Restart the engine (`uv run python -m evf.main --no-window`) and leave it running for the whole task.

- [ ] **Step 1: Get the Pi's LAN IP**

Run on the Pi:
```bash
ip -4 -o addr show scope global | awk '{print $2, $4}'
```

Expected: prints one or more interface/IP pairs. Note the address you'll type into the phone (e.g. `wlan0 192.168.1.42/24` → use `192.168.1.42`).

- [ ] **Step 2: Open the URL on the phone**

On the phone: open `http://<pi-ip>:8765` in any browser.

Expected:
- PushNav React UI renders (Navigation tab is the default).
- The MJPEG element shows live camera frames (a sky scene or the dark cap, depending on what the camera sees).
- The state pill in the header reflects the engine state (e.g., `SETUP` or `SOLVING`).
- The WebSocket connects: the frame counter / state pill update in real time (verify by covering the lens — the brightness changes within ~1 second on screen).

- [ ] **Step 3: Confirm the Settings tab loads**

On the phone: open Settings.

Expected: panel renders; the LAN URL field shows `http://<pi-ip>:8765`; the QR code renders next to it.

- [ ] **Step 4: Confirm the "What to See" tab loads with the catalog**

On the phone: switch to the "What to See" tab.

Expected: the 161-row Stargazing Buddy catalog renders; filter and detail panel are usable; switching to the Advanced sub-tab also works (~12.5k NGC + ~8.8k stars load client-side).

No commit.

---

### Task 7: Real-sky verification — sync wizard and GOTO arrow

**Files:** None changed. This requires actual night sky in the camera's field of view.

- [ ] **Step 1: Plate-solve lock**

Aim the camera at a clear patch of sky. From the phone Navigation tab, watch the state pill.

Expected: engine transitions `SETUP` → `SOLVING` → `LOCKED` (matches the state values in `python/evf/engine/state.py`). The pointing readout shows RA/Dec degrees with non-zero matches.

If it stays in `SOLVING`: confirm focus and exposure are reasonable (the live MJPEG should show several distinct stars), and the camera's lens cap is off.

- [ ] **Step 2: Sync wizard end-to-end**

On the phone: trigger the sync wizard from the Navigation tab and follow the steps it presents (`SPEC_ARCHITECTURE.md` covers the state transitions if you need a reference).

Expected: each wizard step advances cleanly; the wizard concludes with a sync calibration saved (visible afterwards as a non-zero `sync_d_body` offset; the green crosshair in the live view shifts to reflect the eyepiece projection center).

- [ ] **Step 3: GOTO a buddy-catalog target**

On the phone: switch to "What to See", pick any buddy-catalog target currently above the horizon (the visibility math filters to in-view objects), tap "Set as target", return to Navigation.

Expected: the push-to arrow renders (either an in-FOV target marker or an edge arrow pointing offscreen). As you physically move the telescope, the arrow tracks the angle to the target; once you've closed the separation, the target marker appears on screen.

No commit.

---

### Task 8: LX200 client integration test (SkySafari or Stellarium Mobile)

**Files:** None changed. Pick whichever LX200-capable mobile app you already use.

- [ ] **Step 1: Configure the client**

In SkySafari (Settings → Telescope) or Stellarium Mobile (Plus → Telescope Control): add a Meade LX200 Classic over TCP at `<pi-ip>:4030`.

Expected: the client reports the telescope as connected; coordinates update in real time as the Pi-side engine plate-solves.

- [ ] **Step 2: Issue a slew**

From the mobile sky chart, pick a bright target and request a GOTO / slew.

Expected: on the Pi side, the engine logs receive the `:Sr...`/`:Sd...`/`:MS` LX200 commands (visible in the engine terminal). The PushNav Navigation tab now shows the slewed target as the active goto target, with the push-to arrow rendering accordingly.

- [ ] **Step 3: Confirm the round-trip**

Move the telescope manually toward the target; watch both the SkySafari/Stellarium reticle and the PushNav arrow.

Expected: the mobile client's reticle moves in lockstep with the PushNav RA/Dec readout (both come from the same plate-solve), and the arrow shrinks toward the target.

No commit.

---

### Task 9: Capture any aarch64-specific fixes as separate commits

**Files:** Vary depending on what (if anything) broke in Tasks 1–8.

This task is conditional. Examples of fixes that could land here, each as its own small commit on `rpi-appliance`:

- `pyproject.toml`: split the heavy `pywebview[qt]` extra into an optional group keyed off a `gui` extra, so `uv sync` on a headless Pi can stay slim. Only if Task 3 surfaced a wheel-resolution problem.
- `camera/linux/Makefile`: add a missing flag or include path needed on aarch64 trixie. Only if Task 2 failed.
- `python/evf/<module>.py`: tighten a platform check or import guard. Only if a runtime warning escalated to an error in Tasks 5–7.

- [ ] **Step 1: Diff what actually changed**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
git status
git diff
```

Expected: lists every working-tree change. If clean — no fixes were needed — skip the rest of this task and proceed to Task 10.

- [ ] **Step 2: Commit each logical fix separately**

For each independent change, stage just those files and commit with a Conventional Commits-style message matching the existing project history (see `git log --oneline -20`). Example template (replace placeholders with the real fix):

```bash
git add path/to/changed/file
git commit -m "fix(<scope>): <one-line summary of the actual fix>

<2-3 lines of context: what failed on aarch64, how this fixes it,
why it's safe on x86_64/macOS/Windows>"
```

Expected: `git log --oneline` shows one new commit per logical fix. `git status` is clean.

- [ ] **Step 3: Re-run the smoke tests if anything was patched**

If any commits landed in Step 2: re-run Tasks 5 and 6 to confirm the fix didn't regress headless startup or the phone UI.

Expected: clean engine startup, all four ports bound, phone UI loads.

If nothing was committed: no re-run needed.

---

### Task 10: Write the runbook `docs/rpi-headless.md`

**Files:**
- Create: `docs/rpi-headless.md`
- Modify: `mkdocs.yml` or the docs index — only if the repo already lists individual install/hardware pages in a nav config; check before editing

- [ ] **Step 1: Check whether the docs site has a nav config**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
ls docs/_config.yml mkdocs.yml 2>/dev/null
grep -l "install.md\|hardware.md" docs/*.yml docs/index.md 2>/dev/null
```

Expected: tells you whether a nav file references `install.md` / `hardware.md` so you can add the new runbook next to them. If neither file mentions an explicit nav, just link from `docs/install.md`.

- [ ] **Step 2: Write `docs/rpi-headless.md`**

Create the file with exactly the content inside the outer four-backtick fence below. (The outer fence is four backticks so the inner three-backtick code blocks render correctly; save only the inner content — the four-backtick lines themselves are not part of the runbook.)

````markdown
# Running PushNav headless on a Raspberry Pi 4

PushNav runs headless on a Raspberry Pi 4 (Debian 13 / aarch64) and is
controlled entirely from a phone on the same Wi-Fi via the existing
mobile web UI at `http://<pi-ip>:8765`. This page is the install-and-run
runbook; the laptop builds (macOS `.app`, Windows installer, Linux
x86_64 AppImage) are unchanged.

> **Scope.** This is "make it work from source" — no auto-start, no
> mDNS, no pre-flashed SD-card image. Those land in a later appliance
> milestone.

## Prerequisites

- Raspberry Pi 4 (4 GB or more) running Raspberry Pi OS / Debian 13.
- An openaicam USB camera (VID `0x32E6` / PID `0x9251`) — the Linux
  camera server targets this device specifically.
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
- `Stellarium server listening` (port 10001, localhost)
- `LX200 server listening on 0.0.0.0:4030`
- `Mobile web interface at http://<pi-ip>:8765`

Press Ctrl-C to stop. The engine cleans up all subsystems before
exiting.

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
change `webserver.port` in your config file.

**Phone can't reach the URL** — Confirm phone and Pi are on the same
Wi-Fi SSID (not Pi on Ethernet + phone on Wi-Fi unless your router
routes between them). Some captive-portal Wi-Fi APs block client-to-
client traffic; try a regular home network.

**Audio warnings in the log** — Harmless on a headless Pi with no
audio sink. The engine plays lock/lost/goto_ack WAVs through
`playsound3`; if there's no sink it logs once and continues.

**Slow first plate-solve** — tetra3's first lookup loads the ~85 MB
star database into memory. Subsequent solves are fast.

## Limitations

- No auto-start. You run `uv run python -m evf.main --no-window`
  manually after each boot.
- No mDNS / `pushnav.local`. Type the IP into the phone.
- No Wi-Fi onboarding. Configure the Pi's Wi-Fi the usual way
  (Raspberry Pi Imager, `raspi-config`, or `nmcli`).

Each of these is on the roadmap as a later appliance slice.
````

- [ ] **Step 3: Sanity-check the doc renders**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
test -f docs/rpi-headless.md && wc -l docs/rpi-headless.md
grep -c '^##' docs/rpi-headless.md
```

Expected: file exists, ~80 lines, at least 6 `##` section headings (Prereqs, Clone and build, Run, Connect from a phone, Troubleshooting, Limitations).

- [ ] **Step 4: Link from `docs/install.md`**

Open `docs/install.md` and add a one-line "Raspberry Pi headless" pointer near where other platforms are listed. Read the file first to match the existing style.

Run:
```bash
grep -n -iE 'linux|macos|windows' docs/install.md | head -10
```

Use the result to pick the right insertion point — the new line should sit alongside the existing platform sections, not in some random spot. The text:

```markdown
- **Raspberry Pi 4 (headless)**: see [Running PushNav headless on a Raspberry Pi 4](rpi-headless.md).
```

Adapt the exact wording so it matches the surrounding bullets/headings.

- [ ] **Step 5: Commit the runbook + spec + plan together**

Run:
```bash
cd /home/arun/Devel/Github/pushnav
git status
git add docs/rpi-headless.md docs/install.md \
        docs/superpowers/specs/2026-05-17-rpi-headless-design.md \
        docs/superpowers/plans/2026-05-17-rpi-headless.md
git commit -m "docs(rpi): add headless runbook for Raspberry Pi 4

PushNav already supports headless mode via --no-window; this adds the
install-and-run runbook for source-installing on a Pi 4 (aarch64) and
captures the design + plan that drove the verification pass on
rpi-appliance.

No code changes are required: the existing aiohttp webserver, LX200
server and C/V4L2 camera server already cover the appliance happy
path. Auto-start, mDNS and image-build land in later slices."
```

Expected: one commit lands on `rpi-appliance` containing the runbook, install-doc cross-link, and the two superpowers docs. `git status` is clean afterwards.

- [ ] **Step 6: Push the branch (only if the user asks)**

Do NOT push automatically — wait for the user to confirm. When asked:

```bash
git push -u origin rpi-appliance
```

Expected: GitHub prints the branch URL. Stop here; PR creation is a separate decision.

---

## Self-review notes (already addressed)

- Spec coverage: every "In scope" bullet in the spec maps to a task —
  build C server (T2), uv sync (T3), npm build (T4), `--no-window`
  startup (T5), phone smoke test (T6), real-sky verification (T7),
  LX200 client (T8), aarch64 fixes commit (T9), runbook (T10). The
  five-of-six "Known risks" entries from the spec map to specific
  pre-flight checks in T1, T3 and the troubleshooting block in T10.
- Placeholders: none — every command is concrete; the conditional task
  (T9) is conditional by design and the plan explicitly says "skip if
  nothing changed".
- Type consistency: no shared types/symbols introduced across tasks;
  the engine signatures referenced (`--no-window`, port numbers, log
  strings) match `main.py`, `webserver/server.py`, and
  `camera/subprocess_mgr.py`.
