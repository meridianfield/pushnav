# PushNav (EVF) — Plate-Solving Push-To System

## Project Overview

A cross-platform desktop app that plate-solves live camera frames to determine telescope pointing,
enabling push-to navigation for manual telescopes.

Python (React UI in a pywebview window + tetra3 solver) talks to a native camera subprocess over TCP.
Camera servers are platform-specific: Swift (macOS), C/V4L2 (Linux), C/DirectShow (Windows).

External integrations run in-process on three TCP servers: a **Stellarium** binary-protocol
server on `localhost:10001`, an **LX200 Classic** ASCII server on `0.0.0.0:4030` for
SkySafari / Stellarium Mobile / INDI / ASCOM clients, and an **aiohttp HTTP + WebSocket**
server on `0.0.0.0:8765` for the phone-scannable mobile web interface.

The UI has two tabs:
- **Navigation** — live camera frame, plate-solve overlay, sync wizard, push-to arrow.
- **What to See** — filterable catalog of 161 deep-sky objects (vendored from
  the Stargazing-Buddy site) with client-side visibility math. Click a row →
  detail panel; "Set as target" promotes the object to the current GOTO target
  and switches back to Navigation. The right column also hosts a manual
  Location panel; observer location feeds visibility math and falls back to
  Stellarium's reported location when a Stellarium client is connected.

## Build & Run

```bash
uv sync                          # install Python deps from lockfile
(cd web && npm install)          # install Node deps

# Production-style — launches engine + pywebview window with built React UI
(cd web && npm run build)
uv run python -m evf.main

# Dev mode (HMR) — Vite serves UI on :5173 with hot reload
uv run python -m evf.main --dev --no-window     # terminal 1: engine only
(cd web && npm run dev)                          # terminal 2: Vite dev server
# Open http://localhost:5173 in your browser
```

### Platform-specific camera build

```bash
scripts/build_camera_mac.sh         # macOS — Swift camera server
make -C camera/linux                # Linux — C/V4L2 camera server
```

```cmd
camera\windows\build.bat            :: Windows — C/DirectShow camera server (run from VS Developer Command Prompt)
```

### Platform-specific app builds

```bash
scripts/build_mac.sh                # macOS — Nuitka → .app → .dmg
scripts/build_linux.sh              # Linux — Nuitka standalone
scripts/build_windows.bat           # Windows — Nuitka → Inno Setup installer
```

### Running tests

```bash
uv run pytest tests/
```

## Project Layout

```
pyproject.toml                  # project config (hatchling build, uv sources)
python/evf/                     # main Python package
  main.py                       # entry point — engine + pywebview
  paths.py                      # centralized path resolution (dev vs release bundles)
  network.py                    # shared LAN-IP probe used by webserver + engine
  engine/                       # core engine, state machine, threading
    engine.py                   # main engine (owns all subsystems)
    state.py                    # state machine
    frame_buffer.py             # latest-frame buffer (no queues)
    pointing.py                 # telescope pointing state
    navigation.py               # goto-target navigation logic
    goto_target.py              # thread-safe goto target container
    sample_injector.py          # dev-mode sample-image injector
    audio.py                    # audio feedback (lock/lost sounds)
    epoch.py                    # J2000 <-> JNow precession (pyerfa)
  camera/                       # TCP camera client
    client.py                   # camera TCP client
    protocol.py                 # camera protocol (de)serialization
    subprocess_mgr.py           # camera subprocess lifecycle manager
  solver/                       # tetra3 plate-solving
    solver.py                   # solver wrapper
    thread.py                   # solver worker thread
    sync.py                     # multi-star sync / calibration
  stellarium/                   # Stellarium telescope protocol server
    server.py                   # TCP server for Stellarium connection
    protocol.py                 # Stellarium binary protocol
  lx200/                        # LX200 Classic TCP protocol server
    server.py                   # TCP server (select-based, multi-client)
    protocol.py                 # LX200 ASCII parsing + dispatch
  webserver/                    # aiohttp HTTP + WebSocket server
    server.py                   # serves React build, MJPEG, /ws, /api/*
  config/                       # configuration
    manager.py                  # JSON config read/write
    logging_setup.py            # logging configuration
python/vendor/tetra3/           # vendored tetra3 (local editable dep via uv)
web/                            # React + Vite + TS + Tailwind + shadcn/ui front-end
  package.json
  vite.config.ts
  src/
    App.tsx
    main.tsx
    components/                 # LiveView, Wizard, Settings, DebugPanel, ...
      catalog/                  # WhatToSee tab — table, filters, detail, time, LocationPanel
      live-view/                # LiveView, NavOverlay, AxesOverlay, StarOverlay, ...
    hooks/                      # useEngineState (WebSocket subscription), useView
    lib/                        # api client, types, astronomy (altAz/rise/set), catalogTypes
    data/
      objects.json              # vendored deep-sky catalog (161 entries)
  public/                       # logo, inapp-title, favicons
  dist/                         # build output (gitignored)
camera/
  mac/                          # Swift camera server (macOS)
  linux/                        # C/V4L2 camera server (Linux)
  windows/                      # C/DirectShow camera server (Windows)
data/
  hip8_database.npz             # tetra3 star database (~85 MB)
  VERSION.json                  # app + protocol + db version metadata
  sounds/                       # audio feedback WAVs (lock, lost, goto_ack)
  web_dist/                     # React build output (release-only — copied here by build scripts)
docs/                           # GitHub Pages documentation
  index.md                      # GitHub Pages landing page
  hardware.md                   # camera, lens, DIY, shopping list
  design.md                     # KISS philosophy, design decisions
  _config.yml                   # Jekyll config for GitHub Pages
  assets/                       # documentation images
hardware/                       # 3D-printable mechanical designs (OpenSCAD)
  3d_models/                    # OpenSCAD source and pre-built STLs
    housing.scad                # camera housing (base+dovetail, hood+baffle, cap)
    stls/                       # pre-built STL files ready for printing
marketing/                      # app branding assets (logo, in-app title)
linux/                          # Linux desktop integration (pushnav.desktop)
build/                          # build output (gitignored)
scripts/                        # build and dev scripts
  build_mac.sh                  # macOS Nuitka build → .app/.dmg
  build_linux.sh                # Linux Nuitka build
  build_windows.bat             # Windows Nuitka + Inno Setup build
  build_camera_mac.sh           # compile Swift camera server
  run_dev.sh                    # dev launch (macOS)
  run_dev_linux.sh              # dev launch (Linux)
  run_dev_windows.bat           # dev launch (Windows)
  run_mock_camera.sh            # launch mock camera for testing
  pushnav.iss                   # Inno Setup installer script (Windows)
  sync_catalog.py               # vendor objects.json from ~/Devel/Github/stargazing-buddy-site
  test_stellarium_live.py       # manual Stellarium integration test
tests/                          # test suite (pytest)
  samples/                      # plate-solve test images (a–d.png + targets/)
specs/start/                    # design specifications
```

## Key Dependencies

- **tetra3** — vendored at `python/vendor/tetra3/`, wired as editable local dep in `[tool.uv.sources]`
- **pywebview** — wraps the OS webview (WebKit/WebView2/GTK) for the desktop window
- **React + Vite + TypeScript + Tailwind + shadcn/ui** — front-end stack (under `web/`)
- **numpy**, **scipy**, **Pillow** — tetra3 dependencies
- **playsound3** — audio feedback for solve lock/lost events
- **aiohttp** — HTTP + WebSocket server (serves the React build, /ws state, /frame.mjpg, /api/*)
- **qrcode[pil]** — QR-code rendering for the LAN URL in the Settings panel
- **pyerfa** — IAU 2006 precession (J2000 ↔ JNow) for the LX200 protocol server
- **pyyaml** — used only by `scripts/sync_catalog.py` to parse the buddy-site
  markdown frontmatter when refreshing `web/src/data/objects.json`

Dev dependencies: **nuitka** (builds), **pytest** (tests).
Docs dependency group (`uv sync --group docs`): **mkdocs-material** for the
GitHub Pages site under `docs/`.

The runtime app does **not** depend on `~/Devel/Github/stargazing-buddy-site`.
That repo is only consulted by `scripts/sync_catalog.py` when the maintainer
runs the script to refresh the vendored JSON.

## Important: Loading the tetra3 Database

tetra3's `load_database()` resolves string paths relative to its own `tetra3/data/` directory.
Our database lives at `data/hip8_database.npz` in the repo root.

**Always use a `pathlib.Path` object**, not a bare string:

```python
from pathlib import Path
from tetra3 import Tetra3

# CORRECT — Path object bypasses tetra3's internal path resolution
t3 = Tetra3(load_database=Path("data/hip8_database"))

# WRONG — string triggers lookup in tetra3/data/ which won't find our file
t3 = Tetra3(load_database="hip8_database")
```

In application code, use `evf.paths.database_path()` which handles dev vs release path resolution.

## Architecture Rules

- UI must NOT own core logic; core engine runs without UI
- Solver thread never blocks UI thread
- No frame queues — always use most recent frame only
- All shared state protected by `threading.Lock`
- Camera subprocess is a separate OS process, communicating over TCP
- The camera_server binary should `exit(1)` on device disconnect / fatal
  capture error; the engine's `CameraSubprocessMgr` watches the TCP socket
  and runs a 5-attempt backoff recovery loop (1, 2, 4, 8, 15 s)
- Path resolution goes through `evf/paths.py` (handles dev repo, macOS .app bundle, Linux/Windows release)
- All fonts in the React UI come from the OS — the app ships no web fonts and
  applies no `font-family` overrides; Tailwind v4 preflight uses its built-in
  `font-sans` / `font-mono` stacks (system-ui / ui-monospace)

## Specs

Detailed design docs live in `specs/start/`:
- `SPEC_ARCHITECTURE.md` — threading model, state machine, data structures
- `SPEC_PRODUCT.md` — product requirements
- `SPEC_PROTOCOL_CAMERA.md` — camera TCP protocol
- `SPEC_PROTOCOL_STELLARIUM.md` — Stellarium telescope binary protocol (J2000, port 10001)
- `SPEC_PROTOCOL_LX200.md` — LX200 Classic ASCII protocol for SkySafari / Stellarium Mobile / INDI / ASCOM (JNow, port 4030)
- `SPEC_BUILD_RELEASE.md` — build and release process
- `ACCEPTANCE_TESTS.md` — acceptance criteria
