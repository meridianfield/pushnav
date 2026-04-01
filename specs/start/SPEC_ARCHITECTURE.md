# PushNav — Architecture Specification

Version: 2.0
Status: Reflects Current Implementation
Target: macOS, Linux, Windows
Supports Future Headless Mode

---

# 1. Architectural Principles

1. UI must NOT own core logic.
2. Core engine must be runnable without UI.
3. Solver must never block UI.
4. No frame backlog allowed.
5. All inter-thread communication must be explicit and controlled.
6. Camera subprocess is replaceable and platform-specific.

---

# 2. System Overview

```
┌──────────────────────────────────────────────┐
│                 UI Layer                      │
│          (DearPyGui Main Thread)              │
│                                               │
│  - Live view rendering                        │
│  - Step wizard (Camera → Sync → Roll → Track) │
│  - Exposure/Gain controls                     │
│  - Navigation guidance overlay                │
│  - Star overlay (detected + matched)          │
│  - Status display                             │
└───────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│                Core Engine                    │
│                                               │
│  CameraClient  → receives JPEG frames         │
│  SolverThread  → continuous solve loop        │
│  SyncModule    → body-frame calibration       │
│  PointingState → last valid solution          │
│  GotoTarget    → thread-safe GOTO target      │
│  Navigation    → angular separation / guidance │
│  AudioAlert    → lock/lost/ack sounds         │
│  StellariumSrv → TCP broadcast + GOTO handler │
│  ConfigManager → JSON persistence             │
│  Logger        → rotating file logs           │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│       Camera Subprocess (native)              │
│  Platform-specific:                           │
│  - macOS:   Swift / AVFoundation / IOKit      │
│  - Linux:   C / V4L2                          │
│  - Windows: C / DirectShow                    │
│  All use TCP protocol v1 on localhost         │
└──────────────────────────────────────────────┘
```

---

# 3. Process Model

```
Main Python Process
    ├── UI Thread (Main Thread)
    ├── Solver Thread
    ├── Stellarium Thread
    └── Camera TCP Client (non-blocking in UI thread)

Camera Subprocess (separate OS process)
    └── Platform-native TCP server
```

---

# 4. Thread Responsibilities

## 4.1 UI Thread

Responsibilities:

- Step wizard (Camera → Sync → Roll → Track)
- Receive frames from CameraClient
- Store latest JPEG (protected by Lock)
- Decode JPEG → RGB texture for display
- Display solver status, navigation guidance, star overlays
- Modify exposure/gain
- Never call tetra3

Must remain responsive at all times.

### DearPyGui Live Texture Update Pattern

DearPyGui requires textures as flat float32 arrays with RGBA values in [0.0, 1.0].

Setup (once at startup):

    import dearpygui.dearpygui as dpg
    import numpy as np

    WIDTH, HEIGHT = 1280, 720
    CHANNELS = 4  # RGBA

    # Create initial blank texture data
    initial_data = [0.0] * (WIDTH * HEIGHT * CHANNELS)

    with dpg.texture_registry():
        texture_id = dpg.add_raw_texture(
            width=WIDTH, height=HEIGHT,
            default_value=initial_data,
            format=dpg.mvFormat_Float_rgba,
        )

    # Display in window
    with dpg.window(label="Live View"):
        dpg.add_image(texture_id)

Per-frame update (called from render loop callback):

    from PIL import Image
    import io

    def update_texture(jpeg_bytes: bytes):
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        img = img.resize((WIDTH, HEIGHT))

        # Convert to float32 RGBA, normalized to [0.0, 1.0]
        rgb = np.array(img, dtype=np.float32) / 255.0
        alpha = np.ones((*rgb.shape[:2], 1), dtype=np.float32)
        rgba = np.concatenate([rgb, alpha], axis=2)

        dpg.set_value(texture_id, rgba.flatten().tolist())

Rules:
- Call update_texture from the DearPyGui render callback (main thread only).
- Do NOT decode JPEG or call NumPy from the solver thread.
- Texture dimensions are fixed at startup; resize incoming frames to match.
- Use `.tolist()` to pass flat Python list to `set_value` (DearPyGui requirement).

---

## 4.2 Solver Thread

Loop active during CALIBRATE, WARMING_UP, and TRACKING states.

Pseudo-logic:

```
while not stopped:
    if state not in (CALIBRATE, WARMING_UP, TRACKING):
        exit thread

    copy latest_jpeg under lock
    if no frame:
        sleep small interval
        continue

    decode JPEG → grayscale PIL
    centroids = get_centroids_from_image(img, **centroid_params)
    result = solve_from_centroids(centroids, image_size, **solve_params)

    if state == CALIBRATE:
        check_calibration(ra, dec, roll)

    if sync_d_body is set:
        ra, dec = apply_body_frame_sync(sync_d_body, ra, dec, roll)

    if result valid:
        update PointingState (including centroids for star overlay)
        if first success and state == WARMING_UP:
            transition → TRACKING
    else:
        increment failure counter
        if failures >= threshold:
            play lost sound
```

No frame queue.
No blocking UI.
Always use most recent frame only.

---

## 4.3 Stellarium Thread

Runs independent TCP server.

```
every 1 second:
    read last valid RA/Dec from PointingState
    encode per Stellarium binary protocol
    broadcast to connected clients
```

Incoming GOTO commands are decoded and stored in GotoTarget for navigation guidance.
On client connect, plays acknowledgment sound and queries Stellarium Remote Control API
for observer status and object info.

---

# 5. Shared Data Structures

## 5.1 Latest Frame Buffer

```
class LatestFrame:
    jpeg_bytes: bytes
    timestamp: float
    frame_id: int
```

Protected by threading.Lock.

Only one frame stored.
Overwritten on each new frame.

---

## 5.2 Pointing State

```
@dataclass(frozen=True)
class PointingSnapshot:
    ra_j2000: float
    dec_j2000: float
    roll: float
    matches: int
    prob: float
    last_success_timestamp: float
    valid: bool
    all_centroids: list | None        # [y, x] for all detected stars
    matched_centroids: list | None    # [y, x] for matched stars
    image_size: tuple[int, int] | None  # (height, width)
```

Protected by threading.Lock.

Updated only by SolverThread.
Read by UI and StellariumThread.

---

## 5.3 GOTO Target

```
@dataclass(frozen=True)
class GotoTargetSnapshot:
    ra_j2000: float   # degrees
    dec_j2000: float  # degrees
    active: bool
```

Thread-safe container. Updated by Stellarium server thread.
Read by UI for navigation guidance.
Plays acknowledgment sound (`goto_ack.wav`) on each new GOTO.

---

# 6. Engine State Machine

States:

```
SETUP
SYNC
SYNC_CONFIRM
CALIBRATE
WARMING_UP
TRACKING
RECONNECTING
ERROR
```

Transitions:

```
SETUP → SYNC
    Trigger: user initiates sync

SYNC → SYNC_CONFIRM
    Trigger: first valid solve on sync star

SYNC → WARMING_UP
    Trigger: use previous calibration (skip sync)

SYNC_CONFIRM → CALIBRATE
    Trigger: body-frame sync computed, user confirms

SYNC_CONFIRM → WARMING_UP
    Trigger: skip calibration

CALIBRATE → WARMING_UP
    Trigger: finder rotation detected (scope moved + stabilized)

WARMING_UP → TRACKING
    Trigger: first valid solve

TRACKING → SETUP
    Trigger: user stops tracking

ANY → RECONNECTING
    Trigger: camera disconnect

RECONNECTING → SETUP
    Trigger: successful restart

RECONNECTING → ERROR
    Trigger: retries exhausted

ERROR → SETUP
    Trigger: manual user restart
```

### Sync Workflow Detail

1. **SETUP → SYNC**: User selects "Begin Sync". Solver thread runs a background solve
   to identify candidate stars.
2. **SYNC → SYNC_CONFIRM**: Engine presents `SyncCandidate` list. User selects the star
   they centered. Body-frame offset (`sync_d_body`) is computed via `compute_body_frame_sync()`.
3. **SYNC_CONFIRM → CALIBRATE**: Solver thread begins calibration — waits for the user to
   move the telescope at least 0.5° and stabilize for 1s, then computes `finder_rotation`
   from the position angle.
4. **CALIBRATE → WARMING_UP**: Calibration complete (or skipped). Solver thread transitions
   to normal tracking.

If previous calibration is saved in config, user can skip directly: SETUP → SYNC → WARMING_UP.

---

# 7. Camera Subprocess Management

### 7.1 Subprocess Spawn

On app start:

1. Resolve binary path via `evf/paths.py`:
   - Dev: `./camera/mac/camera_server` (or platform equivalent)
   - Release: bundled in app resources directory (platform-specific)
2. Spawn via subprocess.Popen.
3. Wait briefly (up to 2s) for the camera server to bind its TCP port.
4. Connect as TCP client to `127.0.0.1:8764`.
5. Complete HELLO handshake (see SPEC_PROTOCOL_CAMERA.md section 4).
6. Receive CONTROL_INFO, build UI sliders dynamically.
7. Begin receiving FRAME messages.

### 7.2 Termination / Shutdown

On app close or camera restart:

1. Close the TCP socket (this signals the camera server to exit).
2. Call `process.terminate()` (sends SIGTERM).
3. Wait up to 2 seconds: `process.wait(timeout=2)`.
4. If still alive, call `process.kill()` (sends SIGKILL).
5. Collect stdout/stderr for logging.

### 7.3 Crash Recovery

If connection drops:
- Stop tracking.
- Enter RECONNECTING.
- Attempt restart with exponential backoff.
- Max retries: 5.

Backoff schedule:
1s, 2s, 4s, 8s, 15s

Frame stall detection: if no frames received for 2.0s, treat as stalled.

If exhausted:
- Enter ERROR state.

---

# 8. Solver Initialization

At application startup:

```python
from pathlib import Path
t3 = tetra3.Tetra3(load_database=Path("data/hip8_database"))
```

In application code, use `evf.paths.database_path()` which handles dev vs release path resolution.

Database location:
Bundled `data/hip8_database.npz` (~85 MB, 21,200 stars to magnitude 8, ~10.5M patterns)

Load only once. Expect ~2s load time on first call.

### 8.1 Camera Optical Geometry

Field of view:   8.86 x 4.98 degrees
Radius:          5.081 degrees
Pixel scale:     24.9 arcsec/pixel

The `fov_estimate` parameter uses the horizontal FOV (8.86 deg), NOT the diagonal or radius.

### 8.2 Two-Step Solve (Per Frame)

The solver splits into centroid extraction and solving to return both all detected
centroids and matched centroids for star overlay visualization.

Step 1 — Centroid extraction:

```python
centroids = get_centroids_from_image(img, **_CENTROID_PARAMS)
```

Centroid parameters:
```python
_CENTROID_PARAMS = dict(
    sigma=2,
    filtsize=15,
    max_area=2000,  # Allow bright extended stars (M45, Capella)
)
```

Step 2 — Solve from centroids:

```python
result = t3.solve_from_centroids(
    centroids,
    (img.height, img.width),
    return_matches=True,
    fov_estimate=8.86,
    fov_max_error=1.5,
    match_radius=0.01,
    pattern_checking_stars=30,
    match_threshold=0.1,
    solve_timeout=1000,  # ms — cap failed solves to ~1s
)
```

Post-processing — Roll negation:

```python
# tetra3's image-vector convention produces opposite sign to body-frame formulas.
# Empirically verified across 7 targets: std drops from 1.04° to 0.14°.
if result.get("Roll") is not None:
    result["Roll"] = (360.0 - result["Roll"]) % 360.0
```

Result also includes:
- `all_centroids`: Nx2 array (y, x) of all detected stars
- `matched_centroids`: matched stars from `return_matches=True`
- `image_size`: (height, width) tuple

### 8.3 Result Validation

result dict keys: 'RA', 'Dec', 'Roll', 'FOV', 'Matches', 'Prob', 'T_solve', ...

A solve is accepted only when ALL conditions are met:
- result['RA'] is not None (solve succeeded)
- result['Matches'] >= min_matches (configurable, default 8)
- result['Prob'] <= max_prob (configurable, default 0.2)

If any condition fails, the solve is discarded and PointingState is NOT updated.

### 8.4 Image Preparation

Camera delivers JPEG bytes. Before solving:
1. Decode JPEG to PIL Image: `Image.open(io.BytesIO(jpeg_bytes))`
2. Convert to grayscale: `.convert("L")`
3. No additional preprocessing needed (no histogram equalization, no cropping).

---

# 9. Sync and Calibration

## 9.1 Body-Frame Sync (`solver/sync.py`)

Computes a body-frame offset vector from a single sync point (user centers a known star).

Key functions:
- `radec_to_vec()` / `vec_to_radec()` — coordinate conversions
- `orientation_from_radec_roll()` — constructs body-frame rotation matrix
- `compute_body_frame_sync()` — offset vector from sync point
- `apply_body_frame_sync()` — applies calibration to subsequent solve results
- `build_sync_candidates()` / `auto_select()` — extract candidate list from solve result

## 9.2 Finder Rotation Calibration (`solver/thread.py`)

After sync, the calibration phase detects the angular relationship between the
camera's orientation and the telescope mount's movement direction.

Parameters:
- `_CALIBRATE_MIN_SEP = 0.5` — minimum angular separation (degrees) before accepting
- `_CALIBRATE_STABLE_TOL = 0.05` — max frame-to-frame drift (degrees) to count as stable
- `_CALIBRATE_STABLE_SECS = 1.0` — seconds of stability required

Process:
1. User moves telescope while solver runs continuously
2. Once scope moves ≥0.5° from reference and stabilizes for 1s, compute finder_rotation
3. `finder_rotation` is persisted to config for reuse

---

# 10. Navigation (`engine/navigation.py`)

Computes guidance from current pointing to a GOTO target:

- `angular_separation()` — Vincenty formula for sky distance
- `sky_position_angle()` — position angle between two sky positions
- `gnomonic_project()` — tangent-plane projection with FOV handling
- `compute_navigation()` — full navigation result (separation, direction, projected position)
- `edge_arrow_position()` — off-screen target arrow positioning for UI

---

# 11. Audio Feedback (`engine/audio.py`)

Plays sounds on failure-count transitions during tracking:

- 0 → ≥threshold (default 3) → play "lost" sound (stars lost)
- ≥threshold → 0 → play "lock" sound (stars re-acquired)
- GOTO received → play "goto_ack" sound (acknowledgment)

Sounds are in `data/sounds/`: `lock.wav`, `lost.wav`, `goto_ack.wav`.
Audio can be enabled/disabled via config. Uses `playsound3` (non-blocking).

---

# 12. Graceful Shutdown

When the user closes the application, execute the following sequence in order:

### 12.1 Shutdown Sequence

1. **Stop solver thread.**
   - Set `tracking_enabled = False`.
   - Join solver thread with timeout (2s).
   - Log final solve statistics (total solves, success rate).

2. **Close Stellarium server.**
   - Close all connected client sockets.
   - Close server socket.
   - Join Stellarium thread with timeout (2s).

3. **Terminate camera subprocess.**
   - Close TCP socket to camera server.
   - Call `process.terminate()` (SIGTERM).
   - Wait up to 2s: `process.wait(timeout=2)`.
   - If still alive: `process.kill()` (SIGKILL).

4. **Save configuration.**
   - Write current exposure, gain, thresholds, calibration, and display settings to config.json.
   - Only write if values have changed since last save.

5. **Flush logs.**
   - Flush all logging handlers.
   - Close log files.

6. **Exit.**

### 12.2 Rules

- Shutdown must complete within 10 seconds total.
- Each step has independent timeouts — a hung thread must not block later steps.
- No signal handlers (SIGTERM/SIGINT) in v1. DearPyGui's window close event triggers the sequence.
- If any step fails, log the error and continue with the next step.

---

# 13. Configuration Manager

Responsibilities:

- Load JSON config at startup.
- Create default config if missing.
- Validate schema version.
- Merge missing keys from defaults on upgrade.
- Save config on change.
- Provide getters/setters.

Config file location (platform-specific):
- macOS: `~/Library/Application Support/ElectronicViewfinder/config.json`
- Linux: `$XDG_CONFIG_HOME/electronic-viewfinder/config.json`
- Windows: `%APPDATA%/ElectronicViewfinder/config.json`

Default configuration:

```json
{
  "version": 1,
  "solver": {"min_matches": 8, "max_prob": 0.2},
  "camera": {"exposure": 100, "gain": 10},
  "calibration": {"finder_rotation": 0.0, "sync_d_body": null},
  "logging": {"verbose": false},
  "audio": {"enabled": true},
  "display": {"hidpi": false}
}
```

---

# 14. Logging System

Must use Python logging module.

Handlers:
- RotatingFileHandler
- Console (dev only)

Levels:
- INFO (normal mode)
- DEBUG (verbose mode)

Must not log per-frame failures at INFO level.

---

# 15. Future-Proofing

Architecture must allow:

- Headless mode (engine without UI)
- Additional planetarium protocols
- INDI driver
- Equatorial mount support

UI must not tightly couple to solver internals.

---

# 16. Explicit Anti-Patterns (Forbidden)

- No frame queues.
- No blocking calls in UI thread.
- No direct solver calls from UI.
- No global mutable state without locks.
- No editing site-packages tetra3 in production.
- No retry loops without limits.
