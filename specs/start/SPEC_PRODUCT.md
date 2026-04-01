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
- Reports solved RA/Dec (J2000) to Stellarium via its Telescope TCP protocol.
- Accepts GOTO commands from Stellarium for navigation guidance.
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
- "Ack" sound on Stellarium client connect and GOTO received.
- Audio can be enabled/disabled in settings.

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

# 5. Stellarium Integration

- TCP server on localhost.
- Default port: 10001
- Implements Stellarium telescope binary protocol.
- Broadcasts last valid solution every 1 second.
- Processes incoming GOTO commands into navigation targets.
- Queries Stellarium Remote Control API (port 8090) for observer location and object info.
- Plays acknowledgment sound on client connect.

No support for:
- LX200
- ASCOM
- INDI
- SkySafari

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
ANY → RECONNECTING (camera crash)
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
    "exposure": 100,
    "gain": 10
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
    "hidpi": false
  }
}
```

Config is versioned for future upgrades. Missing keys are merged from defaults on load.

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
- Audio feedback on lock/lost transitions.
- Unplug camera → auto restart attempts.
- Exceed retry limit → ERROR state.
- No visible frame lag during tracking.
