# PushNav (EVF) — Plate-Solving Push-To System

## Project Overview

A cross-platform desktop app that plate-solves live camera frames to determine telescope pointing,
enabling push-to navigation for manual telescopes.

Python (DearPyGui UI + tetra3 solver) talks to a native camera subprocess over TCP.
Camera servers are platform-specific: Swift (macOS), C/V4L2 (Linux), C/DirectShow (Windows).

## Build & Run

```bash
uv sync                    # install all deps from lockfile
uv run python -m evf.main  # launch app
uv run python -m evf.main --dev  # launch in dev mode
```

### Platform-specific camera build

```bash
scripts/build_camera_mac.sh         # macOS — Swift camera server
make -C camera/linux                # Linux — C/V4L2 camera server
camera\windows\build.bat            # Windows — C/DirectShow camera server
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
  main.py                       # entry point
  paths.py                      # centralized path resolution (dev vs release bundles)
  engine/                       # core engine, state machine, threading
    engine.py                   # main engine (owns all subsystems)
    state.py                    # state machine
    frame_buffer.py             # latest-frame buffer (no queues)
    pointing.py                 # telescope pointing state
    navigation.py               # goto-target navigation logic
    goto_target.py              # thread-safe goto target container
    audio.py                    # audio feedback (lock/lost sounds)
  ui/                           # DearPyGui UI layer
    window.py                   # main UI window
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
  config/                       # configuration
    manager.py                  # JSON config read/write
    logging_setup.py            # logging configuration
python/vendor/tetra3/           # vendored tetra3 (local editable dep via uv)
camera/
  mac/                          # Swift camera server (macOS)
  linux/                        # C/V4L2 camera server (Linux)
  windows/                      # C/DirectShow camera server (Windows)
data/
  hip8_database.npz             # tetra3 star database (~85 MB)
  VERSION.json                  # app + protocol + db version metadata
  fonts/                        # Inter font files for UI
  sounds/                       # audio feedback WAVs (lock, lost, goto_ack)
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
  test_stellarium_live.py       # manual Stellarium integration test
tests/                          # test suite (pytest)
  samples/                      # plate-solve test images (a–d.png + targets/)
specs/start/                    # design specifications
```

## Key Dependencies

- **tetra3** — vendored at `python/vendor/tetra3/`, wired as editable local dep in `[tool.uv.sources]`
- **DearPyGui** — UI framework (requires display context; import-only works headless)
- **numpy**, **scipy**, **Pillow** — tetra3 dependencies
- **playsound3** — audio feedback for solve lock/lost events
- **pyerfa** — IAU 2006 precession (J2000 ↔ JNow) for the LX200 protocol server

Dev dependencies: **nuitka** (builds), **pytest** (tests)

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
- Path resolution goes through `evf/paths.py` (handles dev repo, macOS .app bundle, Linux/Windows release)

## Specs

Detailed design docs live in `specs/start/`:
- `SPEC_ARCHITECTURE.md` — threading model, state machine, data structures
- `SPEC_PRODUCT.md` — product requirements
- `SPEC_PROTOCOL_CAMERA.md` — camera TCP protocol
- `SPEC_PROTOCOL_STELLARIUM.md` — Stellarium telescope protocol
- `SPEC_BUILD_RELEASE.md` — build and release process
- `ACCEPTANCE_TESTS.md` — acceptance criteria
