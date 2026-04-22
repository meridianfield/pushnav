# ACCEPTANCE_TESTS.md — PushNav

Version: 2.1
Status: Reflects Current Implementation
Applies: macOS, Linux, Windows

Goal:
A developer must be able to run these tests end-to-end without guessing.

## Test automation legend

Each section below is one of:

- **Manual** — requires a user at a telescope or a real third-party client
  (Stellarium, SkySafari, etc.). Run visually, check boxes as you go.
- **Automated** — covered by a `pytest` test under `tests/`; run with
  `uv run pytest tests/`. Automated sections name the concrete test file.

Current coverage:

| Section | Type      | Test file(s) under `tests/`                                  |
|---------|-----------|--------------------------------------------------------------|
| A       | Manual    | —                                                            |
| B       | Mixed     | `test_camera.py`, `test_subprocess_mgr.py` (protocol/mock)   |
| C       | Mixed     | `test_sync.py` (math); manual for the UI wizard flow         |
| D       | Manual    | —                                                            |
| E       | Manual    | —                                                            |
| F       | Mixed     | `test_stellarium.py` (protocol); manual for end-to-end       |
| G       | Mixed     | `test_subprocess_mgr.py` (restart logic); manual for crash   |
| H       | Manual    | `test_audio.py` (loader); manual for actual audio playback   |
| I       | Manual    | —                                                            |
| J       | Manual    | —                                                            |
| K       | Automated | `test_solver_offline.py`, `test_phase1.py`, `test_offline_full.py`, `test_navigation.py`, `test_sync.py` |
| L       | Mixed     | `test_epoch.py`, `test_lx200_protocol.py`, `test_lx200_server.py` (L8); manual for L1–L7                |

---

## A. Startup / Setup Mode

### A1. Launch
- [ ] App launches without crash.
- [ ] Live view window appears within 3 seconds (excluding one-time DB load).
- [ ] App state shows `SETUP`.
- [ ] Four-step wizard visible: Camera → Sync → Roll → Track.
- [ ] Step 1 (Camera) is active by default.

### A2. Database load
- [ ] hip8_database loads once at startup (no reloads during runtime).
- [ ] Load time is logged (INFO).
- [ ] UI stays responsive while DB loads (no frozen window > 0.5s).

---

## B. Live View + Camera Controls

### B1. Frames arriving
- [ ] Live view updates continuously.
- [ ] App does not accumulate memory over time (no unbounded buffering).

### B2. Exposure control
- [ ] Change exposure slider in UI.
- [ ] Image brightness responds within 0.5s.

### B3. Gain control
- [ ] Change gain slider in UI.
- [ ] Image brightness/noise responds within 0.5s.

### B4. Auto exposure forced off
- [ ] Verify auto exposure is forced OFF at backend init.
- [ ] Exposure remains stable (no auto ramp) when stars enter/exit frame.
- [ ] Must be logged once at startup.

---

## C. Sync Calibration Workflow

### C1. Begin Sync
- [ ] Click "Begin Sync" button.
- [ ] State becomes `SYNC`.
- [ ] Solver runs a background solve to identify candidate stars.

### C2. Candidate star selection
- [ ] Candidate stars are presented after solve completes.
- [ ] User selects the star they centered in the eyepiece.
- [ ] State becomes `SYNC_CONFIRM`.
- [ ] Body-frame sync offset is computed.

### C3. Calibration phase
- [ ] State becomes `CALIBRATE`.
- [ ] Solver thread begins continuous solving.
- [ ] User moves telescope at least 0.5° from reference position.
- [ ] Scope stabilizes (drift < 0.05° for 1 second).
- [ ] Finder rotation is computed and saved to config.
- [ ] State becomes `WARMING_UP`.

### C4. Skip calibration
- [ ] If previous calibration exists, "Skip" or "Use Previous Calibration" is available.
- [ ] Clicking skip proceeds to `WARMING_UP` without calibration phase.
- [ ] Saved `finder_rotation` is used.

### C5. First successful solve → TRACKING
- [ ] With a solvable star field, first valid solve occurs.
- [ ] State becomes `TRACKING`.
- [ ] UI displays:
  - RA (J2000)
  - Dec (J2000)
  - last solve time
  - matches
  - prob
  - consecutive failure count
  - time since last solve
- [ ] Subsequent solves update these values.

---

## D. Solve Validation Thresholds

### D1. Threshold enforcement
- [ ] Configure `min_matches` to a high number so solves likely fail.
- [ ] App does not accept solves under threshold.
- [ ] UI shows "solve failed" while keeping last valid RA/Dec unchanged.

### D2. Threshold persistence
- [ ] Change thresholds in settings.
- [ ] Restart app.
- [ ] Thresholds persist (loaded from config.json).

---

## E. Failure Behavior

### E1. Solve failure does not jump
- [ ] During TRACKING, induce a failure (cover lens briefly).
- [ ] UI shows failure.
- [ ] Reported RA/Dec does not change during failure.
- [ ] When solves resume, RA/Dec updates again.

### E2. Sustained failures
- [ ] Keep failure condition for 30 seconds.
- [ ] App remains stable (no crash, no memory blowup).
- [ ] UI continues to show time since last good solve.

---

## F. Stellarium Integration

### F1. Connection
- [ ] Open Stellarium.
- [ ] Telescope Control plugin connects to `localhost:10001`.
- [ ] App logs connection event.
- [ ] Acknowledgment sound plays on connect.

### F2. Pointing updates
- [ ] When app is TRACKING and solving, Stellarium crosshair updates at ~1 Hz.
- [ ] If solves fail, Stellarium holds last valid position.

### F3. GOTO navigation
- [ ] Send a GOTO from Stellarium (click on a star → "Slew telescope").
- [ ] App logs receipt of GOTO.
- [ ] Navigation guidance appears in UI (distance, direction).
- [ ] Target arrow overlay shows on live view when target is off-screen.
- [ ] Acknowledgment sound plays on GOTO received.
- [ ] Object info is fetched from Stellarium Remote Control API.
- [ ] "Clear Target" button dismisses navigation.
- [ ] App does not attempt to control any mount.

---

## G. Camera Subprocess Crash / Restart

### G1. Crash detection
- [ ] Kill camera subprocess manually.
- [ ] App detects disconnect within 2 seconds.
- [ ] Tracking stops.
- [ ] State becomes `RECONNECTING`.

### G2. Restart attempts
- [ ] App attempts restart with backoff: 1s, 2s, 4s, 8s, 15s.
- [ ] Max 5 retries.
- [ ] Each attempt is logged.

### G3. Recovery success
- [ ] When camera is available again, app reconnects.
- [ ] App returns to `SETUP` state (tracking remains OFF).
- [ ] Exposure/gain restored from config.

### G4. Retry exhausted
- [ ] If camera never returns, app enters `ERROR` after max retries.
- [ ] UI shows persistent error message and next action.

---

## H. Audio Feedback

### H1. Lock/lost sounds
- [ ] During TRACKING, induce failures (cover lens).
- [ ] After 3 consecutive failures, "lost" sound plays.
- [ ] When solves resume, "lock" sound plays.

### H2. Audio toggle
- [ ] Disable audio in settings.
- [ ] No sounds play during lock/lost transitions.
- [ ] Re-enable audio → sounds resume.

### H3. GOTO acknowledgment
- [ ] Send GOTO from Stellarium.
- [ ] "goto_ack" sound plays.

---

## I. Logging / Config Files

### I1. Config path
- [ ] Config file exists at the platform-specific path after first run.

### I2. Logs path
- [ ] Logs are created at the platform-specific log directory.
- [ ] Rotating behavior works (size limited, multiple files).

### I3. Verbose toggle
- [ ] Enable verbose logging in settings.
- [ ] Per-solve debug entries appear (timings, matches, prob).

### I4. Calibration persistence
- [ ] Complete sync calibration.
- [ ] Restart app.
- [ ] `finder_rotation` and `sync_d_body` persist in config.json.
- [ ] "Use Previous Calibration" option appears.

---

## J. Performance / Responsiveness

### J1. No backlog
- [ ] While TRACKING, UI remains responsive.
- [ ] No increasing delay between camera motion and updated solve results.
- [ ] Memory remains stable over 10 minutes.

---

## K. Offline Testing (No Camera Required)

These tests verify solver correctness using known sample images, without needing a physical camera or the camera subprocess.

### K1. Sample Test Data

Location: `tests/samples/`

| Image     | Difficulty                  | Known RA  | Known Dec | Notes                                    |
|-----------|-----------------------------|-----------|-----------|------------------------------------------|
| a.png     | Difficult (dark, Capella)   | 79.025    | 46.762    | Requires max_area=2000 for bright star   |
| b.png     | Easy                        | 132.88    | 46.37     |                                          |
| c.png     | Easy                        | 49.76     | 57.84     |                                          |
| d.png     | Moderate (JPEG artifacts)   | 30.83     | 49.19     |                                          |
| orion.png | Additional                  | ~82       | ~-5       | Used by the UI debug-sample injection feature and by some manual SkySafari goto verifications (Orion region). |

There's also a `tests/samples/targets/` subdirectory with smaller crops used
by a subset of targeted solver tests.

RA/Dec values are in degrees (J2000). A correct solve should match within ~2 degrees of the known values.

All sample images solve successfully with `hip8_database` using the parameters from SPEC_ARCHITECTURE.md section 8.2.

### K2. Offline solver test procedure

1. Load `hip8_database` as normal.
2. For each sample image:
   a. Read raw file bytes (`open(path, "rb").read()`) — the solver is given
      the original JPEG/PNG bytes and handles decoding internally via
      `PlateSolver.solve_frame()`. Callers do not need to convert to
      grayscale or extract centroids manually.
   b. Call `solver.solve_frame(image_bytes)` and assert
      `result['RA'] is not None`.
   c. Assert RA within 2 degrees of known value.
   d. Assert Dec within 2 degrees of known value.
3. All four core samples must pass; `orion.png` is optional in automated
   runs since it's primarily a UI-injection fixture.

### K3. Offline Stellarium protocol test

1. Start the Stellarium TCP server thread.
2. Feed a known RA/Dec into PointingState manually.
3. Connect a test TCP client to `localhost:10001`.
4. Verify 24-byte messages arrive at ~1 Hz.
5. Decode and verify RA/Dec match the injected values.

### K4. Offline camera protocol test

1. Write a mock camera server that:
   - Binds to `127.0.0.1:8764`.
   - Sends HELLO, then CONTROL_INFO.
   - Reads sample JPEG files from disk and sends them as FRAME messages at ~10 fps.
2. Start the Python app pointing at the mock server.
3. Verify live view displays frames.
4. Verify SET_CONTROL messages arrive when sliders are moved.

### K5. Sync and calibration tests

1. Verify body-frame sync computation across multiple sky positions.
2. Verify Roll-aware body-frame sync accuracy.
3. Verify candidate star selection and auto-select.
4. Verify finder rotation computation from position angle.
5. Verify calibration handles meridian flip (Roll=180°).

### K6. Navigation tests

1. Verify angular separation (Vincenty formula) across edge cases.
2. Verify gnomonic projection with roll.
3. Verify edge arrow positioning for off-screen targets.
4. Verify RA wrapping at 0/360° boundaries.
5. Verify behavior near poles.

## L. LX200 Protocol

See `specs/start/SPEC_PROTOCOL_LX200.md` §10 for the authoritative list.
Summary of verification points:

- **L1** — SkySafari (iOS/Android/macOS) connected via Settings → Telescope → Presets → Add Device → Other, with Mount Type **AltAz GoTo** and Scope Type **Meade LX200 Classic**, pointed at host:4030: crosshair follows pointing within 2 s; RA/Dec match on-screen within 1 arcmin. (Push-To mount types do not drive the Stop/GoTo button transitions correctly — use AltAz GoTo.)
- **L2** — SkySafari GoTo: tap object → tap GoTo; PushNav logs the GOTO, navigation chevrons appear; SkySafari's button flips from "Stop" to "GoTo" via the `:D#` slew-status reply when plate-solve lands within 0.5° of target.
- **L3** — Stellarium Mobile PLUS: TCP connection to host:4030 auto-detects LX200; position tracks pointing.
- **L4** — INDI `indi_lx200basic` with Connection → TCP host:4030: KStars crosshair matches PushNav pointing.
- **L5** — ASCOM "Meade Generic" driver TCP mode to host:4030: N.I.N.A. mount tab shows matching RA/Dec.
- **L6** — Sending `:ED#` does not break the session; subsequent `:GR#` still works.
- **L7** — SkySafari + KStars attached simultaneously; both see consistent position.
- **L8** — Unit tests (`tests/test_epoch.py`, `tests/test_lx200_protocol.py`, `tests/test_lx200_server.py`) all pass.
- **L9** — Nuitka bundle on all three platforms: packaged binary logs `LX200 server listening on 0.0.0.0:4030` (implicitly tests `import erfa` inside the bundle).
