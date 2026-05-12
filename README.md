# PushNav

![Status](https://img.shields.io/badge/status-🚧%20Work%20in%20Progress-yellow)

A cross-platform plate-solving push-to system for manual telescopes. PushNav uses a live camera feed to continuously plate-solve and determine where your telescope is pointing, reporting coordinates to **Stellarium** on the desktop and to **SkySafari**, **Stellarium Mobile**, **INDI**, or **ASCOM** clients over Wi-Fi in real-time. No encoders, no motors, no GOTO mount required.

Don't have a planetarium app, or don't want to switch between two screens? PushNav can run completely standalone. Pick targets from its built-in **What to See** catalog (a curated short-list of 161 hand-picked objects, a search across more than 20,000 stars and deep-sky objects, or a manual RA/Dec panel), follow the push direction, and watch your scope's pointing on the on-screen **Sky View** dome. No other software required.

> **What is plate-solving?**
>
> Any part of the night sky has a unique arrangement of stars. Plate-solving is a technique that takes a photo, matches that arrangement against a catalog, and reports exactly where the camera is pointing, down to a fraction of a degree. PushNav runs it continuously on the live camera feed, so the app always knows where your telescope is aimed.

![PushNav Mounted](docs/assets/mounted.jpeg)

![PushNav in tracking mode](docs/assets/pushnav.0.2.0-tracking.png)

Above: PushNav in tracking mode. The right-hand **Sky View** dome shows the current pointing (yellow) and the active GOTO target (cream) on a hemispheric grid above the local horizon.

It uses European Space Agency's (ESA) tetra3 fast lost-in-space plate solver for plate-solving. This effecient algorithm produces near real-time solutions on a live video feed.

Power your non-GOTO manual telescope with PushNav and enjoy seamless push-to navigation, even in light-polluted urban skies. All for under **$50** with an off-the-shelf USB UVC camera and lens. The same technology that powers spacecraft navigation and advanced astrophotography apps is now available for your backyard stargazing sessions.

📖 **Full documentation: [meridianfield.github.io/pushnav](https://meridianfield.github.io/pushnav)**

## Push-to ops

Pick a target either inside PushNav or from any planetarium app you already use. PushNav's built-in **"What to See"** catalog covers a curated short-list, a fuzzy search across more than 20,000 stars and deep-sky objects, and a manual RA/Dec panel. Or stay in **Stellarium** on the desktop (or **SkySafari**, **Stellarium Mobile**, **INDI**, or **ASCOM** on a phone or tablet) and send the target from there. Either way, PushNav guides you to push the telescope to it, and your scope's live pointing moves on every connected app's sky chart in real time, staying in sync across all clients.

![PushNav tracking M42 across Stellarium and SkySafari](docs/assets/pushnav_ops.png)

Above: **M42 (Orion Nebula)** is the active target on both **Stellarium** (desktop) and **SkySafari** (phone). As the scope is pushed, each plate-solve updates the telescope crosshair on every connected client simultaneously. No mount control, no GoTo motors. Just a camera and Wi-Fi.

## Cross platform from the ground up

Supports **Windows**, **macOS**, and **Linux**. The core app is written in Python with a React UI hosted in a pywebview window (OS-native WebKit/WebView2/GTK), while the camera server is a native binary for each platform (Swift on macOS, C/V4L2 on Linux, C/DirectShow on Windows) to achieve maximum performance and compatibility with UVC cameras.

## How It Works

1. Observer picks a target from PushNav's built-in **What to See** catalog, or from a planetarium app (Stellarium on the desktop, or SkySafari / Stellarium Mobile PLUS / INDI / ASCOM on a phone or tablet), and sends it to PushNav.
2. PushNav shows how to push the telescope to reach the target in its UI.
3. Your telescope's pointing shows in real time on the on-screen **Sky View** dome. When a planetarium app is connected, it also appears as a live crosshair on the app's sky chart, staying in sync across all clients.

### Internal workflow

1. A USB camera in place of your telescope's finder captures the star field
2. PushNav plate-solves frames using the [tetra3](https://github.com/esa/tetra3) star pattern recognition library in near real-time
3. The difference in pointing is calculated and translated into directional guidance which is shown in the UI
4. Solved RA/Dec coordinates are exposed to connected planetarium apps over standard telescope-control protocols, so your telescope's pointing moves on the app's sky chart in real-time as you push.

## Features

- Near real-time plate solving (~20–140 ms per frame)
- One time, simple calibration. No named stars, just point at any bright star and sync
- GOTO navigation guidance for targets picked inside PushNav's **What to See** catalog or sent from your planetarium app (Stellarium, SkySafari, Stellarium Mobile, etc.)
- Built-in **"What to See"** target picker with three modes: **Buddy** (161 hand-picked deep-sky objects filterable by equipment, light-pollution tolerance and visual reward), **Advanced** (fuzzy search across 12,522 NGC objects from OpenNGC and 8,825 bright stars from HYG), and **Manual coordinates** (HMS/DMS RA/Dec entry for anything not in the catalogs). Visibility (alt/az, rise/transit/set) is recomputed live for your location and time; one click promotes the selected object to the GOTO target. Below-horizon objects can't be set as a target.
- Works with **SkySafari**, **Stellarium Mobile**, **INDI**, and **ASCOM** clients over Wi-Fi via the LX200 protocol, with `:D#` slew-status so SkySafari's "Stop / GoTo" button transitions correctly
- **Mobile web interface**: scan a QR code in the Settings panel to open a live mobile view; no app install required, phone and laptop just need to be on the same Wi-Fi
- Live activity indicators in the app showing when Stellarium or LX200 clients are talking
- IAU 2006 J2000 ↔ JNow precession via `pyerfa` at the LX200 boundary (SkySafari expects JNow, PushNav stores J2000)
- Audio feedback for lock/lost/GOTO events
- Always-visible **Sky View** — an interactive 3D hemispheric dome rendered alongside the wizard, showing where the scope is pointing (yellow marker + semi-transparent red telescope cylinder) and where the target sits (cream marker with name label), with solid/dashed lines from the dome centre. Useful as a spatial check during sync, roll calibration, and tracking alike.
- Saves calibration for quick re-sync
- Works from urban light-polluted skies with the right camera/lens combo (see hardware guide)

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)**: Python package manager
- **Node.js 20+** with `npm` (for the React UI)
- A supported UVC camera

### macOS

- Xcode Command Line Tools (for Swift compiler)

### Linux

```bash
sudo apt install gcc libjpeg-dev gstreamer1.0-tools libfuse2
```

| Package | Why |
|---|---|
| `gcc`, `libjpeg-dev` | Compile the V4L2 camera server (`make -C camera/linux`). MJPEG encoding uses libjpeg. |
| `gstreamer1.0-tools` | Provides `gst-play-1.0`, which `playsound3` shells out to for the lock / lost / GOTO audio alerts. `aplay` (`alsa-utils`) or `ffplay` (`ffmpeg`) also work as fallbacks. |
| `libfuse2` | Only needed if you'll run `scripts/build_linux.sh`'s AppImage stage. Plain dev runs and the `.tar.gz` build don't need it. |

`pywebview` uses its **Qt** backend on Linux. `pywebview[qt]` (QtPy +
PyQt6 + PyQt6-WebEngine) is pulled in automatically by `uv sync` as a
normal pip dependency — there are **no** system PyGObject / GTK /
WebKit2GTK packages to install. PyQt6 itself depends on the usual X11 /
OpenGL / font / audio system libraries (`libxcb-*`, `libgl1`,
`libfontconfig1`, `libxkbcommon-x11-0`, `libnss3`, ...) — every desktop
Linux install ships these by default, so you only need to install them
on minimal / server / container images that don't already have a desktop
session.

### Windows

- [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (cl.exe)
- (Optional) [Inno Setup 6](https://jrsoftware.org/isinfo.php) for building the installer

## Setup

```bash
git clone https://github.com/meridianfield/pushnav.git
cd pushnav
uv sync
(cd web && npm install)
```

## Building the Camera Server

The camera server is a native binary that captures frames and streams them to PushNav over TCP. It must be built before running the app.

**macOS** (Swift / AVFoundation):
```bash
scripts/build_camera_mac.sh
```

**Linux** (C / V4L2):
```bash
make -C camera/linux
```

**Windows** (C / DirectShow): run from a VS Developer Command Prompt:
```cmd
camera\windows\build.bat
```

## Running

PushNav has two run modes against the source tree (no Nuitka compile
needed in either):

### A. One-terminal run with the built React UI (recommended)

Build the React bundle once, then launch the Python app — it serves the
built UI itself and opens it in a pywebview window:

```bash
(cd web && npm run build)
uv run python -m evf.main
```

Re-run `npm run build` whenever you change `web/src/**`.

### B. Two-terminal run with HMR (for active UI work)

Useful when you're iterating on React/Tailwind. The Python engine runs
headless and Vite serves the UI on port `5173` with hot reload:

```bash
# terminal 1 — engine + camera, no window
uv run python -m evf.main --dev --no-window

# terminal 2 — Vite dev server
(cd web && npm run dev)
```

Then open `http://localhost:5173/` in your browser. `--dev` also enables
the in-app DebugPanel and the `/api/dev/*` endpoints (sample injection,
frame capture).

### Convenience scripts

The helper scripts launch `evf.main`; the Python entry-point itself
probes `localhost:5173` and uses Vite's HMR when it's running, falling
back to the prebuilt bundle on `:8765` otherwise. So you can leave Vite
out and everything still works in one terminal:

```bash
scripts/run_dev.sh           # macOS — builds Swift camera, then evf.main
scripts/run_dev_linux.sh     # Linux — uv sync, installs npm deps and builds
                             #         React if missing, then evf.main
                             #         (assumes `make -C camera/linux` ran)
scripts\run_dev_windows.bat  # Windows — assumes camera\windows\build.bat ran first
```

If you want HMR, start `(cd web && npm run dev)` in another terminal
*before* the script — `evf.main` will pick :5173 automatically.

Set `PUSHNAV_DEBUG=1` (or pass `--dev`) for engine dev features, and
`WEBVIEW_DEBUG=1` for the webview inspector — see the next section for
details and a Linux caveat.

### Dev-mode environment variables

Two independent toggles:

- **`PUSHNAV_DEBUG=1`** (equivalent to `--dev`) — enables the engine's
  in-app dev features: the React DebugPanel, the `/api/dev/*` endpoints,
  sample-image injection, and frame capture. Works on macOS, Linux, and
  Windows.
- **`WEBVIEW_DEBUG=1`** — opens the webview inspector inside the
  pywebview window (right-click → Inspect Element). Independent of
  `PUSHNAV_DEBUG`; set both when you want dev features *and* the
  inspector.

**Linux caveat:** `WEBVIEW_DEBUG=1` on Linux starts QtWebEngine's
remote-debugging server, which on this platform truncates aiohttp's
static-file responses to ~440 bytes — the React bundle never finishes
parsing and the window stays blank (dark red `<body>` only). Until
that's resolved upstream, debug the React UI on Linux via the
two-terminal Vite workflow above: leave `WEBVIEW_DEBUG` unset, run
`uv run python -m evf.main --dev --no-window` plus `(cd web && npm run
dev)`, then open `http://localhost:5173/` in regular Firefox or Chrome
and use its native devtools.

## Building Release Binaries

Release builds use [Nuitka](https://nuitka.net/) to compile Python to a standalone binary, then package platform-specific distributables.

**macOS**: produces `PushNav.app` and `PushNav.dmg`:
```bash
scripts/build_mac.sh
```

**Linux**: produces a tar.gz and AppImage:
```bash
scripts/build_linux.sh
```

**Windows**: produces a zip and Inno Setup installer:
```cmd
scripts\build_windows.bat
```

Build output goes to `build/`.

### macOS Gatekeeper note

The macOS `.dmg` is built with an ad-hoc code signature, **not** an Apple
Developer ID. When you (or anyone you share the build with) downloads
the `.dmg` from a browser, macOS Gatekeeper sees the quarantine flag and
shows *"PushNav is damaged and can't be opened. You should move it to
the Bin."* The app is fine — that dialog is just macOS refusing to
launch an unsigned app it considers "downloaded from the internet".

Strip the quarantine flag in Terminal once after copying to
`/Applications`:

```bash
xattr -cr /Applications/PushNav.app
```

Then double-click as normal. (Locally-built `.app`s don't get the
quarantine flag in the first place, so this only affects downloaded
artifacts.)

## Running Tests

```bash
uv run pytest tests/
```

Tests include offline plate-solving against sample images, camera protocol tests with a mock server, Stellarium and LX200 protocol tests, J2000↔JNow precession round-trips, sync/calibration math, and navigation computations. No camera hardware required.

## Stellarium Setup

1. Open Stellarium and enable the **Telescope Control** plugin (restart if needed)
2. Add a telescope: type **"External software or a remote computer"**
3. Host: `localhost`, Port: `10001`
4. Connect

For GOTO navigation guidance, also enable the **Remote Control** plugin (default port 8090).

To use **SkySafari**, **Stellarium Mobile**, **INDI**, or **ASCOM** instead, point your client at PushNav's LX200 server (shown in the app's Settings panel, port `4030`). Full walkthrough: [SkySafari & Other Apps](docs/skysafari-setup.md).

## Project Structure

```
python/evf/            Python application
  engine/              Core engine, state machine, plate-solve pointing, epoch helpers
  camera/              TCP client + subprocess lifecycle for the native camera server
  solver/              tetra3 plate-solve wrapper + body-frame sync
  stellarium/          Stellarium binary TCP server (port 10001)
  lx200/               LX200 Classic TCP server (port 4030, SkySafari / INDI / ASCOM)
  webserver/           aiohttp HTTP + WebSocket server (serves React, /ws, /frame.mjpg, /api/*)
  config/              JSON config + logging setup
  network.py           Shared LAN-IP probe used by webserver and engine
web/                   React + Vite + TypeScript + Tailwind + shadcn/ui front-end
python/vendor/tetra3/  Vendored tetra3 star pattern library
camera/mac/            Swift camera server (macOS)
camera/linux/          C/V4L2 camera server (Linux)
camera/windows/        C/DirectShow camera server (Windows)
data/                  Star database, sounds, version metadata (web_dist/ added on release builds)
hardware/3d_models/    3D-printable camera housing and accessories (OpenSCAD + STLs)
scripts/               Build and dev scripts
tests/                 Test suite
specs/start/           Design specifications
```

## 3D-Printable Hardware

The [`hardware/3d_models/`](hardware/3d_models/) directory contains OpenSCAD source and pre-built STLs for the camera housing and accessories. The hood, cap, and lens accessories print without supports; the base needs localised slicer supports at the USB cutout and (for the threaded variant) the back chord-flat. Any modern slicer places these automatically.

| Part | Description |
|------|-------------|
| **PCB Base + Threaded Lip + Dovetail** (threaded, recommended) | Cylindrical 50 mm shell; internal 44 mm female thread accepts the hood; finder-shoe dovetail (`housing_v2_base.stl`). |
| **Hood + Male Thread + Baffle** (threaded, recommended) | Matching male thread; stepped flange and baffled lens shroud (`housing_v2_hood.stl`). |
| **Dust Cap** (threaded) | Friction-fit cap over the hood's narrow end (`housing_v2_cap.stl`). |
| **PCB Base + Dovetail** (bolted, legacy) | Older design with two variants: self-tapping (2.7mm, `housing_base_selftap.stl`) or bolt-through (3.5mm, `housing_base_bolt.stl`). |
| **Hood + Baffle** (bolted, legacy) | Hood with bolt-plate flange (`housing_hood.stl`). |
| **Dust Cap** (bolted, legacy) | Original friction-fit cap (`housing_cap.stl`). |
| **M12 Lock Ring** | Secures the lens at the correct focus position (`lock_ring.stl`). |

Pre-built STLs are in [`hardware/3d_models/stls/`](hardware/3d_models/stls/). See the [3D models README](hardware/3d_models/README.md) for print settings and build instructions.

## License

Copyright (c) 2026 Arun Venkataswamy
This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Third-party data

The Advanced catalog search is backed by two vendored astronomical
databases. Each lives under `data/catalogs/<name>/` with its upstream
`LICENSE` and a `NOTICE` file recording the exact vendored version.

| Catalog | Upstream | License |
|---|---|---|
| OpenNGC | <https://github.com/mattiaverga/OpenNGC> | CC-BY-SA 4.0 |
| HYG v3  | <https://github.com/astronexus/HYG-Database> | CC-BY-SA (see `data/catalogs/hyg/LICENSE`) |

The build script `scripts/build_catalogs.py` trims these CSVs to the
JSON projections under `web/src/data/`; those derived files inherit
the CC-BY-SA licence.

