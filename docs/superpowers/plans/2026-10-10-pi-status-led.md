# Pi Status LED Implementation Plan

> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the headless Raspberry Pi package, show PushNav's state on
the Pi's built-in LEDs, so a user with no screen can tell at a glance
whether PushNav is up, whether the camera is seen, whether it needs a
sync, and whether it's tracking. Aimed at non-technical users: no extra
hardware such as an I2C/SPI display.

**Branch:** `feat/pi-status-led` (from `main` at `a513176`)

**Decisions (2026-10-10):**
1. Use **both LEDs, red optional.** Red means "needs attention"; green
   means "progress / OK". On a Pi with only a green LED (Pi Zero 2 W),
   the red patterns fall back to distinct green patterns.
2. "Tracking, all good" is a **short blip every 3 s**, to keep dark
   adaptation intact.
3. Control is **config file only** for v1: `led.enabled` in config.json,
   default `true`, documented in the Pi guide. No web UI work.

**Spike (2026-10-10, Pi 5):** a root step that sets `trigger=none` and
does chgrp/`chmod g+w` on `brightness` is enough for an unprivileged
process to drive both LEDs. The five patterns below were all easy to
tell apart.

**Out of scope:** desktop builds (never touch LEDs), web UI controls or
legend, hotspot/appliance states, a hang watchdog.

---

## LED patterns

Evaluated in priority order; the first match wins. Durations are in
seconds.

| # | Condition | Meaning for the user | Both LEDs | Green only (fallback) |
|---|---|---|---|---|
| 1 | `state == ERROR` | Problem: open the app | red steady | green steady |
| 2 | camera not connected, or `state == RECONNECTING` | No camera: check the cable | red slow blink (0.5 on / 1.5 off) | green double blink (0.15/0.15/0.15, then 1.55 off) |
| 3 | `state == TRACKING` and `consecutive_failures >= 3` | Lost the sky: check pointing / dew | green fast blink (0.1 / 0.1) | same |
| 4 | `state == TRACKING` | Tracking, all good | green blip (0.06 on / 2.94 off) | same |
| 5 | any other state (SETUP, SYNC, SYNC_CONFIRM, CALIBRATE, WARMING_UP) | Ready: open the app and sync | green slow blink (0.5 / 1.5) | same |

Whichever LED isn't in the pattern is held off. The threshold of 3 is
the same one `SolverThread._AUDIO_FAIL_THRESHOLD` uses for the "lost"
sound.

Before PushNav starts, the Pi shows its normal boot behaviour. When the
service stops (cleanly or by crash), the LEDs go back to the Pi's normal
behaviour, so a frozen "all good" can never be left showing.

---

## Findings that shape the plan

- `Engine.state_machine.state`, `Engine.camera_connected` and
  `Engine.consecutive_failures` already expose everything the mapping
  needs.
- `ConfigManager._load` merges missing keys from `DEFAULT_CONFIG`, so
  adding `"led": {"enabled": True}` needs no config-version bump.
- LED names: `ACT` (green) and `PWR` (red) on Pi 3A+/4/5 with current
  kernels; older kernels use `led0` / `led1`. The Zero 2 W has `ACT` only.
- The service uses `ProtectSystem=strict`, which leaves `/sys` writable
  (no `ProtectKernelTunables`). Confirm on the Pi.
- Blinking is driven from Python, writing only `brightness`. The kernel
  `timer` trigger would keep blinking after a crash, and it creates
  `delay_on`/`delay_off` files whose permissions would also need fixing.

---

### Task 1: Pattern mapping and LED driver

**Files (new):** `python/evf/engine/status_led.py`, `tests/test_status_led.py`

- [x] `Pattern`: which LED (`"green"` / `"red"`) plus a repeating
      sequence of on/off durations; steady = a single `(on, inf)` step.
- [x] `pattern_for(state, camera_connected, failures, has_red) -> Pattern`:
      a pure function implementing the table above, including the
      green-only fallbacks.
- [x] `find_leds(root=Path("/sys/class/leds")) -> dict`: green from
      `ACT`/`led0`, red from `PWR`/`led1`. Only includes an LED whose
      `brightness` is writable (`os.access(W_OK)`).
- [x] `StatusLedController(snapshot_fn, leds, poll_s=0.1)`: a daemon
      thread that re-reads the snapshot every `poll_s`, steps the current
      pattern with monotonic timing, and writes `brightness` only when a
      value changes. A write `OSError` logs once and disables the
      controller. `stop()` turns both LEDs off and joins the thread.
- [x] Tests: the full mapping table for both LED sets; on a fake sysfs
      tree in `tmp_path`, the controller writes the expected on/off
      values, writes only on change, follows a pattern switch within one
      poll, disables itself on an unwritable file, and `stop()` leaves
      both LEDs at 0. `find_leds` handles ACT/PWR, led0/led1, ACT-only,
      and read-only files.

### Task 2: Root helper to take over and restore the LEDs

**Files (new):** `python/evf/engine/led_helper.py`; tests in `tests/test_status_led.py`

Run as root by systemd: `python3 -m evf.engine.led_helper take|restore [--group pushnav]`.

- [x] `take`: if `led.enabled` is false in the service's config.json
      (read-only `json.load` from `$XDG_CONFIG_HOME/electronic-viewfinder/config.json`;
      a missing file means enabled; never create or save the config as
      root), do nothing. Otherwise, for each LED present:
      - save `trigger`, `brightness`, and the owner and mode of
        `brightness` to `/run/pushnav-headless-led/<name>.json`, **only
        if no saved file exists yet**, so a repeated `take` never records
        "none" as the original
      - set `trigger=none`, `brightness=0`, chgrp to `--group`, and
        `chmod g+w`
- [x] `restore`: for each saved file, restore the owner, mode,
      brightness and trigger, then delete the file. No saved state means
      nothing to do. Never fails the unit (exit 0, errors logged).
- [x] `--root` (sysfs) and `--state-dir` options for tests.
- [x] Tests on a fake sysfs tree: the take/restore round-trip returns
      everything to the original; a second `take` keeps the first saved
      state; `restore` without state is a no-op; `led.enabled=false`
      skips `take`; missing LEDs are skipped. Skip the chgrp/chown checks
      when not running as root.

### Task 3: Wire into the engine and config

**Files:** `python/evf/engine/engine.py`, `python/evf/main.py`, `python/evf/config/manager.py`

- [x] `DEFAULT_CONFIG["led"] = {"enabled": True}` and a
      `ConfigManager.led_enabled` property.
- [x] `Engine.start_status_led()`: if `led_enabled` and `find_leds()`
      returns at least one writable LED, start the controller with a
      snapshot of `(state, camera_connected, consecutive_failures)`.
      Otherwise log one info line ("Status LED: not available" or
      "disabled") and do nothing.
- [x] `Engine.shutdown()`: stop the controller first.
- [x] `main.py`: call it only on the `--no-window` path, next to
      `start_camera_watchdog()`. A source/dev run without the helper
      finds no writable LEDs and does nothing.

### Task 4: Packaging

**Files:** `packaging/headless/pushnav-headless.service`, `scripts/build_headless_deb.sh` (if needed)

- [x] Unit:
      `ExecStartPre=+/usr/lib/pushnav-headless/python/bin/python3 -m evf.engine.led_helper take --group pushnav`
      and
      `ExecStopPost=+/usr/lib/pushnav-headless/python/bin/python3 -m evf.engine.led_helper restore`.
      The `+` prefix runs only these steps as root, without the sandbox.
      The unit's `Environment=` (XDG paths) applies to them, so `take`
      finds the service config.
- [x] Confirm the helper module ships in the bundle (it's part of `evf`,
      so it should with no build change).

### Task 5: Docs

**Files:** `docs/rpi-headless.md`, `CLAUDE.md`

- [x] Pi guide: a "Status light" section with the pattern table in plain
      words; how to turn it off (`"led": {"enabled": false}` in
      config.json, then restart the service); a note that some cases hide
      the LEDs; that the green LED stops showing SD activity while
      PushNav runs; and that on a Pi 4 the red LED's under-voltage
      warning is replaced while PushNav runs.
- [x] CLAUDE.md: one line under the headless notes.

### Task 6: Verify on the Pi 5 (and the 3A+ if available)

- [x] `uv run pytest tests/` passes (351).
- [x] Pi 5 (trixie), .deb reinstalled:
  - [x] `led_helper` takes ACT and PWR at service start; PushNav logs
        "Status LED: using green, red".
  - [x] Camera unplugged: red slow blink (confirmed by eye).
  - [x] Camera plugged in: green slow blink (confirmed by eye).
  - [x] `sudo systemctl stop`: ACT back to `mmc0`, PWR `none`,
        `root:root 644`; green back to normal (confirmed by eye).
  - [ ] Tracking patterns (blip, fast blink) on real hardware need sky or
        sample injection. The blink shapes were confirmed in the spike, and
        the mapping is unit-tested.
- [x] **Pi 3A+** (trixie, 64-bit), .deb reinstalled over SSH: `led_helper`
      takes ACT and PWR; with no camera, PWR is written 0.5 s on / 1.5 s
      off (sampled), and the red LED was confirmed blinking by eye, green
      off. PWR reads back `255` when on (3-series firmware LED); harmless.
      LED thread CPU about 0%; PushNav RSS ~130 MB of 415 MB.
- [ ] Not done (user's call): `led.enabled=false`, reboot, crash tests.
      Finding: `systemctl kill -s KILL` also kills the ExecStopPost
      restore, so the LEDs stay in their last state until the restart
      (5 s), when they're taken over again with the original state still
      saved. A real crash (main process only) should run restore normally;
      not verified.
