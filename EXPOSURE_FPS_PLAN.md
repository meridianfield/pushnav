# Exposure/FPS fix (#26) — implementation plan & context

> **Scratch/working note, scoped to the `camera-exposure-fps` branch. DELETE before merging to `main`.**
> This file exists so the work survives a context `/clear`. A fresh session should read this
> top-to-bottom, then implement. Branch: **`camera-exposure-fps`** (off `main`, after PR #32 merged).

## Goal

Fix GitHub issue **#26**: camera exposure too low → few/no stars on the **Arducam OV9281**
(and any high-default-fps UVC camera). The detection half of #26 (and #30) was already solved
by the camera-allowlist PR #32 (now on `main`). This branch is the **exposure/fps half only**.

## Root cause (confirmed by code reading 2026-06-20)

Max exposure time on a UVC camera is bounded by the frame interval (≈ 1/fps). Faint stars need
long integration (tens–hundreds of ms), which requires a **low fps**. None of the three servers
pins low fps correctly:

| Platform | Where | Current behavior | Bug |
|---|---|---|---|
| **Linux** | `camera/linux/camera_server.c` → `open_camera` (~L336) | `VIDIOC_S_FMT` sets 1280×720 MJPEG; **no `VIDIOC_S_PARM`** | fps left at driver default; exposure (`V4L2_CID_EXPOSURE_ABSOLUTE`) clamped to frame period |
| **Windows** | `camera/windows/camera_server.c` → `try_format` (~L488) / `open_camera` (~L526) | `SetFormat` uses media type as-is; **`AvgTimePerFrame` never set** | fps left at default; `CameraControl_Exposure` clamped to frame period |
| **macOS** | `camera/mac/Sources/CameraServer/CaptureManager.swift` → `configureFormat` (L257-264) | sets `activeVideoMin/MaxFrameDuration = bestRange.minFrameDuration` | **`minFrameDuration` = MAX fps** — pins the *highest* rate (backwards); also sorts by `minFrameRate` not `maxFrameRate` |

Waveshare's default fps was low enough that exposure worked → bug was hidden. Arducam is a 120-fps
global-shutter module → high default caps exposure to a few ms → no stars. Matches Arun's hypothesis
in the #26 thread ("default FPS issue not exposed by Waveshare… select the lowest FPS in 1280×720").

**Important ordering detail:** on V4L2 the exposure control's reported **max often depends on fps**,
so set low fps **before** querying the exposure range, or the UI slider ceiling stays artificially low.

## Decisions (from Arun, 2026-06-20)

1. **[1] Hard-pin the camera's absolute LOWEST fps** at startup (option A). Simplest, max exposure
   headroom. Accept a laggy preview / slower re-solve cadence — fine for a push-to tool.
2. **[4] Show correct exposure units per-OS in the UI** — IN SCOPE for this branch.
3. **[5] Do NOT expose fps in UI/HELLO.** But **log the chosen fps/interval to stderr** for debug.

## Implementation

### A. FPS pinning (decision [1], [5])

- **Linux** (`open_camera`, after the `VIDIOC_S_FMT` that succeeds): call `VIDIOC_S_PARM`
  (`V4L2_BUF_TYPE_VIDEO_CAPTURE`) with `parm.parm.capture.timeperframe` = longest interval (lowest
  fps). Best: enumerate `VIDIOC_ENUM_FRAMEINTERVALS` for the chosen pixfmt/W/H and pick the **max**
  interval; fallback: request `{numerator=1, denominator=5}` and accept the driver's clamp. Guard:
  only if `parm.parm.capture.capability & V4L2_CAP_TIMEPERFRAME`. Read back and **log** the actual
  interval ("Frame rate: N/D = X fps"). If it fails, continue (don't fatal). THEN query exposure
  range (move/keep `query_control(V4L2_CID_EXPOSURE_ABSOLUTE,...)` after S_PARM).
- **Windows** (`try_format`, before `SetFormat`): from the `VIDEO_STREAM_CONFIG_CAPS` for the matched
  cap (the `pSCC` buffer already populated by `GetStreamCaps`), read `MaxFrameInterval` and set
  `pVIH->AvgTimePerFrame = MaxFrameInterval` (lowest fps) on the media type before `SetFormat`.
  **Log** the chosen AvgTimePerFrame (100-ns units → fps = 1e7 / AvgTimePerFrame). Fallback: if caps
  unavailable, leave as-is. Query exposure after.
- **macOS** (`configureFormat`, L257-264): fix the inversion — pick the range that minimizes fps and
  set `activeVideoMinFrameDuration = activeVideoMaxFrameDuration = bestRange.maxFrameDuration`
  (longest duration = lowest fps). Pick `bestRange` by **lowest `maxFrameRate`**. Update the existing
  `print("Configured … @ Nfps")` to log the real (low) fps.

### B. Per-OS exposure units (decision [4])

Exposure control units differ; the UI currently shows raw values:
- **Linux** `V4L2_CID_EXPOSURE_ABSOLUTE`: units of **100 µs** → ms = value × 0.1.
- **macOS** UVC `CT_EXPOSURE_TIME_ABS`: units of **100 µs** (UVC standard) → ms = value × 0.1.
- **Windows** DirectShow `CameraControl_Exposure`: **log₂(seconds)** → ms = 2^value × 1000
  (e.g. -1 → 500 ms, -13 → ~0.12 ms).

Plan: each server adds a `unit` field to the **exposure** control in its CONTROL_INFO JSON, e.g.
`"unit":"100us"` (linux/mac) or `"unit":"log2s"` (windows). The UI converts raw `cur` → a
human-readable time (ms/s) for display. The slider keeps operating on raw `min/max/step` so
`SET_CONTROL` semantics are unchanged — only the **displayed label** is converted. Gain stays as-is.

- `ControlDescriptor` (web/src/lib/types.ts:39) **already has `unit?: string`** — no type change needed.
- CONTROL_INFO JSON to extend:
  - Linux: `camera/linux/camera_server.c` ~L801-809 (add `"unit":"100us"` for exposure only).
  - Windows: `camera/windows/camera_server.c` ~L1061-1069 (add `"unit":"log2s"` for exposure only).
  - macOS: control info is built in `camera/mac/Sources/CameraServer/ControlManager.swift` (find the
    exposure entry; add `unit`). VERIFY the JSON builder there.
- Verify the dict passes through unmodified: `python/evf/camera/protocol.py` (CONTROL_INFO parse) and
  `python/evf/webserver/server.py` (~L546/L585 builds the `controls` list sent to the UI). Likely
  forwards arbitrary keys, but confirm `unit` isn't dropped.
- UI render: `web/src/components/controls/CameraControls.tsx` — for the exposure control, compute and
  show the converted time from `cur` + `unit` (100us → `cur*0.1` ms; log2s → `2**cur*1000` ms, show
  s when ≥ 1000 ms). Keep the slider bound to raw values.

## Verification

- Hardware available here: **Waveshare OV9281 on the Linux box** (`/dev/video0`, `32E6:9251`). No
  Arducam. So we can prove: (a) fps actually drops (log + frame cadence), (b) the exposure ceiling
  rises after pinning low fps, (c) the working camera still streams + plate-solves. The definitive
  "Arducam shows stars" needs Egress-Source's hardware → ships as "should fix, pending reporter
  confirmation," like the allowlist.
- Linux quick checks: `make -C camera/linux`, run the binary, confirm the new fps log line and a
  larger exposure `max`. `v4l2-ctl -d /dev/video0 --list-formats-ext` lists intervals (note: device
  was momentarily un-openable from the sandbox shell on 2026-06-20 — retry).
- `uv run pytest tests/` must stay green (260 passing baseline). Build web: `(cd web && npm run build)`.
- Windows + macOS: native builds verified separately by Arun (same per-OS flow as the allowlist;
  see git history of the deleted CAMERA_ALLOWLIST_TESTING.md for the build/run commands).

## Out of scope / follow-ups

- Coupling fps to exposure dynamically (option C) — deferred; revisit only if low-fps cadence annoys.
- Normalizing exposure to a single unit end-to-end — not doing; per-OS `unit` + UI conversion instead.
- Issue **#29** (Stellarium Mobile Plus won't connect) — unrelated, untouched.

## Status checklist (update as you go)

- [x] Linux: S_PARM lowest-fps + log + re-query exposure
      — `set_lowest_fps()` in camera_server.c; enumerates intervals, picks max
      (lowest fps), S_PARM + read-back log. probe_controls() already runs after
      (in handle_client), so exposure is queried post-S_PARM. Verified on
      Waveshare: "Frame rate pinned: 1/60 s/frame = 60.00 fps" (picks 60 of 60/120).
- [x] Windows: AvgTimePerFrame lowest-fps + log
      — try_format reads MaxFrameInterval from the matched cap's pSCC
      (VIDEO_STREAM_CONFIG_CAPS) and sets pVIH->AvgTimePerFrame before SetFormat.
      VERIFIED natively 2026-06-20 (MSVC 14.50, x64): builds clean; ffmpeg shows
      openaicam 1280x720 MJPEG = 60-120 fps and it pins the lowest —
      "Frame rate pinned: AvgTimePerFrame=166666 (100ns) = 60.00 fps". Streams
      valid JPEG; measured ~32 fps, exposure-limited at cur=-5 (31.25 ms) — i.e.
      the low-fps pin grants exposure headroom past the 8.3 ms that 120 fps would
      impose. No regression. CAVEAT: pins the *matched cap's* MaxFrameInterval
      rather than scanning all caps for the global lowest (macOS scans) — correct
      for this spanning-range camera, but could miss the lowest on a camera that
      exposes discrete per-fps caps high-first. Matches the plan; low priority.
- [x] macOS: fix frame-duration inversion + log
      — configureFormat now picks the range with the smallest minFrameRate via
      `.min(by:)` and pins min/max to its **maxFrameDuration** (longest dur =
      lowest fps). NOTE: deviated from plan's "lowest maxFrameRate" heuristic to
      "lowest minFrameRate" — this hits the device's *absolute* lowest fps
      (decision [1]) and avoids missing a lower rate in an overlapping range.
      VERIFIED natively 2026-06-20 (Apple Swift 6.1.2, arm64): builds clean;
      openaicam (ranges [120-120],[60-60]) → picks 60, logs "Configured
      1280x720 @ 60fps (lowest available)"; capture starts, streams; no
      regression. CAVEAT: both cameras on hand (openaicam, Kreo Owl) report
      discrete single-value ranges, where minFrameDuration==maxFrameDuration, so
      old vs new code pin the *same* fps — the inversion divergence (old pins
      high end on a *spanning* range like [5-120], new pins low) can't be
      reproduced here. Confirms build/run/lowest-selection/log; the decisive
      divergence + "Arducam shows stars" still need the reporter's hardware.
- [x] Linux/Windows/macOS: add `unit` to exposure CONTROL_INFO
      — Linux/macOS correctly send "100us" (gain "raw"). Windows was WRONG: it
      tagged exposure "100us", but DirectShow CameraControl_Exposure is
      log2(seconds), so the UI rendered cur=-5 as -0.5 ms. FIXED 2026-06-20:
      Windows now sends "unit":"log2s" (build_control_info_json), and
      CameraControls.tsx shows 2^value*1000 ms (~0.12-500 ms). Verified natively:
      CONTROL_INFO reports log2s; the dev app shows real ms.
- [x] Confirm `unit` survives protocol.py + webserver → UI
      — client._update_controls stores raw `data.get("controls", [])` dicts
      unmodified; webserver forwards them; types.ts ControlDescriptor has `unit?`.
- [x] UI: CameraControls.tsx shows converted exposure time
      — formatControlValue(): 100us→cur*0.1 ms, log2s→2^cur*1000 ms (s when
      ≥1000 ms); slider stays on raw min/max/step. tsc + vite build green.
- [x] Linux real-camera verify + pytest green
      — engine spawns the rebuilt binary, camera connects, /frame.mjpg streams
      761 KB multipart over the webserver (frames flow end-to-end). pytest 260
      passed. NOTE: this driver reports exposure max=5000 *fixed* regardless of
      fps (so "ceiling rises" isn't observable here); the real win is the
      effective integration window doubling (8.3→16.6 ms at 60 vs 120 fps).
      Definitive "Arducam shows stars" still needs the reporter's hardware.
- [ ] Delete this file before merge
