# Windows startup fixes — Mac/Linux smoke-test note

> **Scratch note, scoped to the `fix/webview-startup-flash` branch. DELETE this file before merging to `main`.**
> Windows is fully verified (built the Nuitka package + ran it: icon, no white flash, ~4 s window, no
> console flash, v0.2.1). This note is the quick **Mac/Linux smoke test** for the one change that
> touches the *shared* startup path. Hand it to Claude Code (or follow it yourself) on each machine.

## What this branch changes

Four commits, all Windows-verified:

- `a01fffa` **fix(ui): eliminate white flash** — `web/index.html` ships `class="dark"` + a
  `color-scheme:dark` meta + an inline dark background, and `main.py` sets the pywebview window
  `background_color`, so the window paints dark from the first frame instead of flashing white.
- `4d3f768` **perf(startup): open window immediately, connect camera in the background** — `main.py`
  moves `startup_camera()` into a background **daemon thread** that runs after `webview.start()`, so the
  window appears in ~3 s instead of blocking ~8–20 s on the camera. Also `CREATE_NO_WINDOW` on the
  Windows `taskkill` (Windows-only).
- `c62f9e3` **chore(release): bump version to 0.2.1**.
- `e5b9465` **chore: sync uv.lock to 0.2.1**.

## Cross-platform risk (why this note is short)

| Change | Mac/Linux risk | Note |
|---|---|---|
| `taskkill` `CREATE_NO_WINDOW` | **none** | inside `if sys.platform == "win32"` — Mac/Linux use the unchanged `pkill` path |
| version bump + `uv.lock` | **none** | pure data/strings |
| `index.html` dark + `oklch()` bg | **very low** | same `oklch()` the whole theme already renders on WebKit (mac) / QtWebEngine (linux) |
| window `background_color` | **low** | standard pywebview param across Cocoa / Qt / WinForms backends |
| **camera → background daemon thread** | **the one to check** | only change to the shared startup flow; a bg thread now runs alongside the GUI event loop |

The deferred work is non-GUI (subprocess + TCP), so it *should* be safe — but Cocoa (macOS) and Qt
(Linux) are strict about the main thread, so confirm the window/loop interaction with one real run.

## Smoke test — run on macOS, then Linux

Prereqs (per platform):
```bash
git checkout fix/webview-startup-flash && git pull
uv sync
(cd web && npm install && npm run build)    # REBUILD web/dist — the flash fix lives in index.html
# Build the native camera server for this OS:
scripts/build_camera_mac.sh                  # macOS (Swift)
make -C camera/linux                         # Linux (V4L2)
```

Run (production-style window):
```bash
uv run python -m evf.main
```

**Confirm the 3 things that matter:**
1. **Window opens, no hang** — appears within a few seconds and the app stays responsive. *This is the
   real check:* the new background camera thread and the GUI event loop coexist cleanly.
2. **No white flash** — the window paints dark from the first frame (watch the moment it opens).
3. **Camera connects in the background** — the live feed appears a few seconds *after* the window (it no
   longer blocks the window). On **macOS**, the camera-permission prompt should still appear on first run,
   and granting it should connect the feed (the prompt comes from the Swift camera subprocess, not the
   Python thread, so it should be unaffected — but confirm).

**Also worth a glance:**
- Title bar shows **PushNav 0.2.1**.
- Clean shutdown on window close — no orphaned `camera_server` process left behind.
- **With no camera attached**, the window should STILL open fast (camera retry is now backgrounded) —
  this is the key win; verify it doesn't stall the window like before.

## Report back

- **macOS** (note Swift/OS version): window opens (no hang)? flash gone? camera connects + permission OK?
- **Linux**: same three, plus pywebview's Qt backend launches cleanly.
- Any **hang / crash / stall on startup** points at the camera-thread × GUI-loop interaction — capture the
  console output and we adjust (e.g. switch the explicit daemon thread to pywebview's `start(func=...)`).
- If both pass: **delete this file** and open the PR.
