# PushNav

A cross-platform plate-solving push-to system for manual telescopes. PushNav uses a live camera feed to continuously plate-solve and determine where your telescope is pointing, reporting coordinates to Stellarium in real-time. Point your scope at any bright star, sync, and PushNav will track your pointing as you push to your next target — no encoders, no motors, no GOTO mount required.

![Screenshot](docs/assets/pushnav_aldebran.png)

It uses European Space Agency's (ESA) tetra3 fast lost-in-space plate solver for plate-solving. This effecient algorithm produces near real-time solutions on a live video feed.

Power your non-GOTO manual telescope with PushNav and enjoy seamless push-to navigation, even in light-polluted urban skies. All for under **$50** with an off-the-shelf USB UVC camera and lens. The same technology that powers spacecraft navigation and advanced astrophotography apps is now available for your backyard stargazing sessions.

## Cross platform from ground up

Supports **Windows**, **macOS**, and **Linux**. The core app is written in Python with a DearPyGui UI, while the camera server is a native binary for each platform (Swift on macOS, C/V4L2 on Linux, C/DirectShow on Windows) to achieve maximum performance and compatibility with UVC cameras.

## How It Works

1. Observer selects an object in Stellarium and "Slews" (Cmd+1 or Ctrl+1)
2. PushNav shows how to push the telescope to reach the target in its UI. 
3. Alternatively the telescope's pointing is also shown in Stellarium as a telescope crosshair that moves in real-time as you push the scope.

#### Internal workflow

1. A USB camera in place of your telescope's finder captures the star field
2. PushNav plate-solves frames using the [tetra3](https://github.com/esa/tetra3) star pattern recognition library in near real-time
3. The difference in pointing is calculated and translated into directional guidance which is shown in the UI
4. Solved RA/Dec coordinates are also broadcast to Stellarium via its telescope protocol, so you can see your telescope's pointing in Stellarium's sky chart in real-time as you push.

## Features

- Near real-time plate solving (~20–140 ms per frame)
- One time, simple calibration. No named stars, just point at any bright star and sync
- GOTO navigation guidance from Stellarium
- Audio feedback for lock/lost/GOTO events
- Saves calibration for quick re-sync
- Works from urban light-polluted skies with the right camera/lens combo (see hardware guide)

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- A supported UVC camera

### macOS

- Xcode Command Line Tools (for Swift compiler)

### Linux

- GCC, libjpeg-dev, libfuse2

```bash
sudo apt install gcc libjpeg-dev libfuse2
```

### Windows

- [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (cl.exe)
- (Optional) [Inno Setup 6](https://jrsoftware.org/isinfo.php) for building the installer

## Setup

```bash
git clone https://github.com/meridianfield/pushnav.git
cd pushnav
uv sync
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

**Windows** (C / DirectShow) — run from a VS Developer Command Prompt:
```cmd
camera\windows\build.bat
```

## Running (Dev Mode)

Dev mode runs the Python source directly (no Nuitka compilation needed):

**macOS** (builds the camera server automatically):
```bash
scripts/run_dev.sh
```

**Linux** (build camera server first):
```bash
make -C camera/linux
scripts/run_dev_linux.sh
```

**Windows** (build camera server first):
```cmd
camera\windows\build.bat
scripts\run_dev_windows.bat
```

Or run directly:
```bash
uv run python -m evf.main --dev
```

## Building Release Binaries

Release builds use [Nuitka](https://nuitka.net/) to compile Python to a standalone binary, then package platform-specific distributables.

**macOS** — produces `PushNav.app` and `PushNav.dmg`:
```bash
scripts/build_mac.sh
```

**Linux** — produces a tar.gz and AppImage:
```bash
scripts/build_linux.sh
```

**Windows** — produces a zip and Inno Setup installer:
```cmd
scripts\build_windows.bat
```

Build output goes to `build/`.

## Running Tests

```bash
uv run pytest tests/
```

Tests include offline plate-solving against sample images, camera protocol tests with a mock server, Stellarium protocol tests, sync/calibration math, and navigation computations. No camera hardware required.

## Stellarium Setup

1. Open Stellarium and enable the **Telescope Control** plugin (restart if needed)
2. Add a telescope: type **"External software or a remote computer"**
3. Host: `localhost`, Port: `10001`
4. Connect

For GOTO navigation guidance, also enable the **Remote Control** plugin (default port 8090).

## Project Structure

```
python/evf/          Python application (engine, UI, camera client, solver, Stellarium server)
python/vendor/tetra3/ Vendored tetra3 star pattern library
camera/mac/          Swift camera server (macOS)
camera/linux/        C/V4L2 camera server (Linux)
camera/windows/      C/DirectShow camera server (Windows)
data/                Star database, fonts, sounds, version metadata
hardware/3d_models/  3D-printable camera housing and accessories (OpenSCAD + STLs)
scripts/             Build and dev scripts
tests/               Test suite
specs/start/         Design specifications
```

## 3D-Printable Hardware

The [`hardware/3d_models/`](hardware/3d_models/) directory contains OpenSCAD source and pre-built STLs for the camera housing and accessories. All parts are designed for FDM printing without supports.

| Part | Description |
|------|-------------|
| **PCB Base + Dovetail** | Holds the camera PCB with an integrated finder shoe dovetail rail. Two variants: self-tapping screw holes (2.7mm) or bolt-through (3.5mm for M3). |
| **Hood + Baffle** | Lens shroud with an integral stepped light baffle that follows the camera's FOV cone to block stray light. |
| **Dust Cap** | Friction-fit cap for the lens opening. |
| **M12 Lens Adapter** | Replacement lens mount for cameras without standard M12 threading. |
| **M12 Lock Ring** | Secures the lens at the correct focus position. |

Pre-built STLs are in [`hardware/3d_models/stls/`](hardware/3d_models/stls/). See the [3D models README](hardware/3d_models/README.md) for print settings and build instructions.

## Documentation

- [Hardware Setup & Camera Guide](docs/hardware.md) — supported cameras, lens, DIY notes, shopping list
- [Design Philosophy](docs/design.md) — why PushNav is built the way it is

Full documentation is also available at [meridianfield.github.io/pushnav](https://meridianfield.github.io/pushnav).

## License

Copyright (c) 2026 Arun Venkataswamy
This project is licensed under the [GNU General Public License v3.0](LICENSE).

