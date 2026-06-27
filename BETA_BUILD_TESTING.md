# tetra3rs beta — Windows / Linux build & solve verification

> **Scratch note, scoped to the `feat/tetra3rs-merge-main` branch. DELETE this file before merging to `main`.**
> **macOS is already verified locally** (build + 269 tests + live solve, version `0.3.0-beta`).
> This note is the **Windows + Linux** build-and-verify pass for the one thing that's new and
> unproven: that the Nuitka standalone correctly packs the compiled **tetra3rs (Rust)** extension
> and that the packaged binary **actually plate-solves** — not just launches. Hand it to a Windows
> box and a Linux box (or follow it yourself on each).

## What this branch changes (vs the last release, 0.2.1)

- **Solver swapped** tetra3 (Python) → **tetra3rs 0.7.1 (Rust / pyo3)**, shipping
  `data/tetra3rs_gaia.bin` (~53 MB) instead of the old `hip8` database.
- Merged `main`'s 0.2.1 work: startup-flash fixes (incl. Linux/QtWebEngine), camera allowlist +
  exposure-fps, exposure-ms UI.
- Version bumped to **0.3.0-beta**.

## Why *this* is the thing to check

| Concern | Status | Note |
|---|---|---|
| Rust toolchain needed to build? | **No — verified** | tetra3rs ships prebuilt wheels for `win_amd64` + `manylinux_2_28` (x86_64/aarch64), cp312/cp313, and `requires-python` is pinned `>=3.12,<3.14`. `uv sync` **downloads** the wheel; `cargo`/`rustc` never run. |
| App deps / no-Rust closure | **verified** | `gaia-catalog` is pure-Python and not bundled (runtime doesn't import it); everything else is already-wheeled. |
| **Nuitka packs the native extension + `.bin`** | **the one to check** | Packing a compiled `.so`/`.pyd` + a 53 MB data blob into a standalone bundle is exactly where cross-platform Nuitka builds silently drop files. The only proof is a **packaged binary that solves**. |

## Build (each script is self-contained)

**Linux:**
```bash
sudo apt install gcc libjpeg-dev libfuse2        # + uv, nuitka already installed
git checkout feat/tetra3rs-merge-main && git pull
scripts/build_linux.sh        # uv sync + camera + web + Nuitka + tar.gz + AppImage
```

**Windows** (run from a **VS Developer Command Prompt** — needed for the C camera server):
```cmd
:: uv + nuitka installed; optional Inno Setup 6 for the installer
git checkout feat/tetra3rs-merge-main && git pull
scripts\build_windows.bat
```

## Confirm — in priority order

1. **No Rust compilation.** During the `uv sync` phase, `tetra3rs` installs from a **wheel** — you
   should NOT see `Building wheel for tetra3rs`, `cargo`, or `rustc`. If you do, the build landed
   outside the wheel matrix (wrong Python/platform) — **stop and report**, don't let it compile.
2. **Build finishes and the bundle contains the solver.** In the assembled release dir
   (`build/PushNav-linux/` or `build\PushNav-windows\`), confirm both exist:
   - the `tetra3rs` package with a **compiled module** — `*.so` (Linux) / `*.pyd` (Windows)
   - `data/tetra3rs_gaia.bin` (~53 MB)
3. **★ IT ACTUALLY SOLVES ★** — the whole point. Launch the **built** binary (not `uv run`) in
   **dev mode** so the sample injector feeds the bundled test frames — **no camera needed**:
   ```bash
   ./build/PushNav-linux/PushNav --dev            # Linux (or the AppImage: ./build/PushNav-x86_64.AppImage --dev)
   ```
   ```cmd
   build\PushNav-windows\PushNav.exe --dev        :: Windows
   ```
   Expect a plate-solve **LOCK** on the injected sample (overlay shows matched stars + RA/Dec).
   This is what proves the packed tetra3rs `.so`/`.pyd` + the `.bin` work *inside the bundle*. If
   the window opens but it **never solves**, packaging dropped the extension or the `.bin` —
   capture the console output and report.
4. **Live solve with a real camera** (if one's attached): launch **without** `--dev` and confirm a
   live frame locks.
5. **Window opens, no white flash** (Linux/QtWebEngine fix), and the title bar reads
   **PushNav 0.3.0-beta**.
6. **Clean shutdown** on window close — no orphaned `camera_server` process left behind.

## Report back

- **Linux** (distro + glibc): build OK? installed from wheel (no `cargo`)? bundle has tetra3rs
  `.so` + `.bin`? `--dev` solve **locks**? live solve? flash gone? title `0.3.0-beta`?
- **Windows** (version): same three, with `.pyd` instead of `.so`.
- Any **"launches but won't solve"** is precisely the native-extension / `.bin` packing failure
  we're hunting — capture the console output so we can fix the Nuitka `--include` for that file.
- If both pass: **delete this file**, then tag and cut the **0.3.0-beta** release.
