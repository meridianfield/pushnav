# ACCEPTANCE_TESTS.md — PushNav

Version: 2.0
Status: Reflects Current Implementation
Applies: macOS, Linux, Windows

Goal:
A developer must be able to run these tests end-to-end without guessing.

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

| Image   | Difficulty                  | Known RA  | Known Dec | Notes                                    |
|---------|-----------------------------|-----------|-----------|------------------------------------------|
| a.png   | Difficult (dark, Capella)   | 79.025    | 46.762    | Requires max_area=2000 for bright star   |
| b.png   | Easy                        | 132.88    | 46.37     |                                          |
| c.png   | Easy                        | 49.76     | 57.84     |                                          |
| d.png   | Moderate (JPEG artifacts)   | 30.83     | 49.19     |                                          |

All four images solve successfully with `hip8_database` using the parameters from SPEC_ARCHITECTURE.md section 8.2.

RA/Dec values are in degrees (J2000). A correct solve should match within ~2 degrees of the known values.

### K2. Offline solver test procedure

1. Load `hip8_database` as normal.
2. For each sample image:
   a. Open with PIL: `Image.open(path).convert("L")`
   b. Extract centroids and solve with spec parameters.
   c. Assert `result['RA'] is not None`.
   d. Assert RA within 2 degrees of known value.
   e. Assert Dec within 2 degrees of known value.
3. All four must pass.

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
