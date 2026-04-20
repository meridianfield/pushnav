# PushNav — Product Specification

Version: 2.0
Status: Reflects Current Implementation
Target: macOS, Linux, Windows

---

# 1. Product Overview

PushNav is a cross-platform telescope pointing system that:

- Streams live camera video for telescope alignment and focus.
- Continuously plate-solves frames when tracking is enabled.
- Provides two-phase sync calibration to align camera pointing with the telescope.
- Reports solved RA/Dec to external clients over three in-process TCP servers:
  Stellarium (binary protocol, J2000), LX200 (SkySafari / Stellarium Mobile /
  INDI / ASCOM, JNow), and a mobile-web interface (HTTP + WebSocket).
- Accepts GOTO commands from Stellarium and LX200 clients for navigation guidance.
- Maintains last valid pointing on solve failure.
- Displays star overlays and navigation guidance in-app.

This system acts as a real-time electronic encoder replacement using plate solving.

---

# 2. Scope

## 2.1 Platform

- macOS, Linux, and Windows
- Single supported UVC camera model
- No camera selection UI
- No multiple camera support

## 2.2 Functional Capabilities

### Live View
- Continuous MJPEG stream from camera subprocess.
- Displayed in DearPyGui panel.
- No frame buffering beyond latest frame.
- Optional star overlay (detected + matched centroids).
- Optional zoom slider for preview.

### Camera Controls
- Exposure (absolute)
- Gain
- Auto-exposure must be forced OFF at camera initialization.
- Controls are built dynamically from camera server's CONTROL_INFO.

### Sync Calibration Workflow

Four-step wizard: Camera → Sync → Roll → Track

#### Step 1: Camera (SETUP)
- Live stream active.
- Exposure and Gain adjustable.
- User can begin sync or use previous calibration.

#### Step 2: Sync (SYNC → SYNC_CONFIRM)
- Engine solves a frame and presents candidate stars.
- User selects the star they centered in the eyepiece.
- Body-frame offset is computed from the selected star.

#### Step 3: Roll / Calibrate (CALIBRATE)
- User moves telescope while solver runs.
- System detects movement direction and computes finder rotation.
- Can be skipped if previous calibration is saved.

#### Step 4: Track (WARMING_UP → TRACKING)
- Continuous solving loop runs in background thread.
- Each new frame is eligible for solving.
- Only latest frame is processed (missed frames ignored).
- First valid solve → state becomes TRACKING.
- RA/Dec broadcast to Stellarium every 1 second.

### Navigation / GOTO Guidance
- Stellarium GOTO commands are decoded and stored as navigation targets.
- UI displays angular separation, direction (Right/Left, Up/Down), and projected target position.
- Target arrow overlay shows direction when target is off-screen.
- "Clear Target" button to dismiss navigation.
- Acknowledgment sound plays on GOTO received.

### Audio Feedback
- "Lock" sound when stars are re-acquired after failure.
- "Lost" sound when consecutive failures reach threshold (3).
- "Ack" sound on Stellarium client connect and on any GOTO received
  (both via Stellarium's binary GOTO and via LX200 `:MS#`, routed through
  `GotoTarget.set()` which plays the sound internally).
- Audio can be enabled/disabled in settings.

### Mobile Web Interface
- Built-in HTTP + WebSocket server on `0.0.0.0:<webserver.port>` (default 8080).
- Serves `data/web/index.html` — a single-page mobile view with no install.
- WebSocket pushes pointing / navigation / state JSON at ~10 Hz to connected clients.
- Settings panel shows the LAN URL + QR code so a phone can scan-to-connect.
- Falls back to "No LAN connection" in the UI when the LAN IP probe fails.
- Up to 10 concurrent WebSocket clients.

---

# 3. Solve Validation Rules

A solve is considered VALID only if:

- result['RA'] is not None
- result['Matches'] >= min_matches
- result['Prob'] <= max_prob

Defaults:

- min_matches = 8
- max_prob = 0.2

These values are user-adjustable in Settings.

No additional validation:
- No jump filtering
- No FOV sanity checks
- No motion heuristics

If solve fails:
- Last valid RA/Dec remains active.
- UI shows failure status and consecutive failure count.
- Stellarium continues receiving last valid coordinates.

---

# 4. Coordinate Semantics

- All internal coordinates are J2000.
- No apparent-of-date transformation.
- Stellarium output uses J2000 encoding only.

---

# 5. External Integrations

PushNav exposes pointing to external clients over three independent TCP servers,
all running in-process: Stellarium (binary protocol, J2000), LX200 (SkySafari /
Stellarium Mobile / INDI / ASCOM, JNow), and a mobile-web interface (HTTP +
WebSocket).

## 5.1 Stellarium (desktop, binary protocol)

- TCP server on `127.0.0.1:10001` (loopback only — desktop Stellarium on the
  same machine).
- Implements the Stellarium telescope binary protocol.
- Broadcasts the last valid solution every 1 second.
- Processes incoming GOTO commands into navigation targets (advisory only;
  never mutates pointing or calibration).
- Queries the Stellarium Remote Control API (port 8090) for observer
  location and object info.
- Plays an acknowledgment sound on client connect.

See `SPEC_PROTOCOL_STELLARIUM.md`.

## 5.2 LX200 (SkySafari / Stellarium Mobile / INDI / ASCOM)

- TCP server on `0.0.0.0:4030` (LAN-reachable so mobile apps can connect).
- Implements the Meade LX200 Classic ASCII command subset used by SkySafari,
  Stellarium Mobile PLUS, INDI `indi_lx200basic`, and ASCOM "Meade Generic" /
  "Meade Classic and Autostar I" drivers.
- Request/response only — never emits unsolicited bytes.
- Reports pointing in JNow (the LX200 convention); PushNav's internal
  canonical form remains J2000. Precession is applied at the LX200 boundary
  via `pyerfa` (IAU 2006).
- `:MS#` (slew-to-target) stores the received target in `GotoTarget` for
  on-screen navigation guidance — same advisory path as the Stellarium GOTO.
- `:CM#` (align/sync) is acknowledge-only per the one-way data flow rule
  (SPEC_PROTOCOL_LX200.md §1.1): external clients never mutate PushNav's
  calibration.
- `:D#` (slew-status) reports "on target" when the plate-solve is within
  0.5° of the committed goto target, so SkySafari's "Stop"/"GoTo" button
  transitions correctly even though PushNav has no motor.

See `SPEC_PROTOCOL_LX200.md`.

## 5.3 Mobile web interface

- HTTP + WebSocket server on `0.0.0.0:<webserver.port>` (default 8080).
- Serves `data/web/index.html` — a single-page mobile companion view with no
  install needed, designed for at-the-eyepiece use.
- WebSocket `/ws` pushes pointing, navigation, and state JSON at ~10 Hz to
  every connected client (cap: 10 concurrent).
- WebSocket Origin header is inspected on connect: non-local origins are
  logged as WARNING but **not rejected** (current behaviour — see
  SPEC_ARCHITECTURE §4.5 for the known hardening gap). Actual protection
  against public-internet exposure relies on the bind address, the host
  firewall, and the concurrent-client cap below.
- The Settings panel shows the LAN URL plus a QR code for scan-to-connect.
- Falls back to "No LAN connection" in the UI when `local_ip()` can't find
  a routable LAN address.

## 5.4 UI surface

The main window's Settings panel exposes all three server addresses:

- `<LAN-IP>:<webserver.port>` — mobile web URL, with QR code
- `localhost:10001` — Stellarium binary protocol (loopback only)
- `<LAN-IP>:4030` — LX200 (LAN-reachable)

The Stellarium and LX200 rows each have a small red-dot activity indicator
that lights while a client is connected (Stellarium) or has sent a command
within the last 100 ms (LX200, which accommodates SkySafari's polling mode
that opens a fresh TCP connection per command).

---

# 6. State Machine

States:

- SETUP
- SYNC
- SYNC_CONFIRM
- CALIBRATE
- WARMING_UP
- TRACKING
- RECONNECTING
- ERROR

Transitions:

```
SETUP → SYNC (user initiates sync)
SYNC → SYNC_CONFIRM (first valid solve on sync star)
SYNC → WARMING_UP (use previous calibration)
SYNC_CONFIRM → CALIBRATE (body-frame sync computed)
SYNC_CONFIRM → WARMING_UP (skip calibration)
CALIBRATE → WARMING_UP (finder rotation detected)
WARMING_UP → TRACKING (first valid solve)
TRACKING → SETUP (user stops tracking)
SETUP|SYNC|SYNC_CONFIRM|CALIBRATE|WARMING_UP|TRACKING → RECONNECTING (camera crash)
RECONNECTING → SETUP (recovery success)
RECONNECTING → ERROR (retry exhausted)
ERROR → SETUP (manual restart)
```

---

# 7. Failure Handling

## 7.1 Solve Failure
- Do not modify RA/Dec.
- Increment failure counter.
- Update UI status.
- After 3 consecutive failures, play "lost" sound.

## 7.2 Camera Subprocess Crash
- Stop tracking immediately.
- Attempt restart.
- Max 5 retries.
- Exponential backoff (1s, 2s, 4s, 8s, 15s).
- Frame stall timeout: 2.0s.
- If retries exhausted → ERROR state.

On successful restart:
- Restore exposure/gain from config.
- Remain in SETUP mode.
- User must re-enable tracking.

---

# 8. Configuration Persistence

Stored as JSON. Platform-specific paths:

- macOS: `~/Library/Application Support/ElectronicViewfinder/config.json`
- Linux: `$XDG_CONFIG_HOME/electronic-viewfinder/config.json`
- Windows: `%APPDATA%/ElectronicViewfinder/config.json`

```json
{
  "version": 1,
  "solver": {
    "min_matches": 8,
    "max_prob": 0.2
  },
  "camera": {
    "exposure": null,
    "gain": null
  },
  "calibration": {
    "finder_rotation": 0.0,
    "sync_d_body": null
  },
  "logging": {
    "verbose": false
  },
  "audio": {
    "enabled": true
  },
  "display": {
    "hidpi": false,
    "hidpi_last_scale": 0
  },
  "webserver": {
    "port": 8080
  }
}
```

Notes:

- `camera.exposure` / `camera.gain` are `null` on first run. The engine
  initializes them to the midpoint of the reported camera range on the
  first camera HELLO and persists the values from there on.
- `display.hidpi_last_scale` caches the last detected display scale factor
  (Windows primary monitor, in percent — 100, 125, 150, …) so the engine
  can auto-toggle 4K mode when the user moves to a different-DPI display.
- `webserver.port` is validated to 1024–65535 on write.
- Config is versioned for future upgrades. Missing keys are merged from
  defaults on load.

---

# 9. Logging Requirements

Log directory (platform-specific, same root as config).

Rotating logs:
- 5MB per file
- 3 file retention

Normal mode logs:
- App start/stop
- Camera connect/disconnect
- Tracking enable/disable
- Successful solve summary
- Solve failure summary (rate limited)
- Stellarium connect/disconnect
- Sync and calibration events

Verbose mode logs:
- Per-solve timing
- Matches
- Probability
- Frame timestamps
- Rejection reason

---

# 10. Performance Targets

- Solver must not create frame backlog.
- UI must remain responsive during solving.
- Latest-frame model strictly enforced.
- Solve latency target: <200 ms per frame on target hardware.

---

# 11. UI Features

- Four-step wizard with step indicators (Camera → Sync → Roll → Track)
- Live camera preview with optional zoom slider
- Star overlay toggle (detected + matched centroids)
- Sync candidate star selector
- Navigation guidance display (distance, direction, projected target)
- Target arrow overlay for off-screen GOTO targets
- Coordinate axes overlay showing mount orientation
- Advanced settings section (solver parameters)
- Mobile-interface address + QR code, with "No LAN connection" fallback
- Telescope-control address block showing LX200 (`<LAN-IP>:4030`) and
  Stellarium (`localhost:10001`) addresses, each with a red-dot activity
  indicator that lights while a client is talking to the server
- HiDPI / 4K monitor compatibility toggle
- Audio enable/disable toggle
- "Use Previous Calibration" button (when saved calibration exists)
- Debug section (dev mode only) for frame capture and sample injection
- Consecutive failure counter and last solve age display

---

# 12. Explicit Non-Goals

- No multiple camera support
- No headless mode (architecture supports future)
- No multi-planetarium abstraction
- No motion smoothing
- No FOV auto-calibration
- No hardware mount control

---

# 13. Acceptance Checklist

- App launches → live view visible.
- Exposure/Gain change affects image.
- Sync workflow → select star → calibrate → TRACKING.
- Use Previous Calibration → skip sync → TRACKING.
- Stellarium crosshair updates at ~1 Hz.
- GOTO from Stellarium → navigation guidance displayed.
- SkySafari (or any LX200 client) connects to `<LAN-IP>:4030`; GOTO from
  SkySafari → navigation guidance displayed and `:D#` reports on-target
  when the plate-solve converges within 0.5°.
- Mobile web interface reachable from a phone on the same Wi-Fi via the
  QR code in the Settings panel.
- Audio feedback on lock/lost transitions.
- Unplug camera → auto restart attempts.
- Exceed retry limit → ERROR state.
- No visible frame lag during tracking.
