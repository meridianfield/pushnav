# Camera allowlist — Mac/Windows testing note

> **Scratch note, scoped to the `camera-allowlist` branch. Delete this file before merging to `main`.**
> Hand this to Claude Code (or follow it yourself) on the macOS and Windows machines.

## Context

We replaced the single hardcoded camera VID/PID in all three native camera servers
with a **built-in allowlist** of OV9281 USB modules, extendable at runtime via the
`PUSHNAV_CAMERA_IDS` env var (and, in the app, via the `camera.extra_camera_ids` config
key, which the engine forwards as that env var). This fixes non-Waveshare cameras not
being detected — GitHub issues **#30** and **#26**.

It was fully verified on **Linux** with a real camera, including the decisive
"supply the camera only via env, with its built-in entry removed" path. **macOS is now
also fully verified** (2026-06-20, Apple Swift 6.1.2 / arm64 — see the ✅ block in the
macOS section). **Windows was written carefully but not yet compiled or run** — that's
what remains.

## Get the code

```
git fetch origin
git checkout camera-allowlist     # commit 10f951c
git pull
```

## Built-in allowlist (all three servers must agree)

| VID | PID | Camera |
|-----|-----|--------|
| `32E6` | `9251` | Waveshare OV9281 |
| `0C45` | `6366` | Arducam OV9281 |
| `1BCF` | `2CD1` | DECXIN OV9281 |

**Env override format:** `PUSHNAV_CAMERA_IDS="1bcf:2cd1,0c45:6366"` — comma-separated
`vid:pid` hex pairs (a `0x` prefix is accepted; entries are de-duplicated against built-ins).

---

## Windows — `camera/windows/camera_server.c`

**Build** (in "x64 Native Tools Command Prompt for VS"):
```
cd camera\windows
build.bat
```
**Run:** `camera_server.exe`  (listens on `127.0.0.1:8764`; Ctrl+C to stop)

**Expect on startup:**
- `Camera allowlist (3 entries):` listing the 3 built-ins
- `Found camera '<name>' (XXXX:XXXX)` — confirm the hex VID:PID is correct
- `Using MJPEG capture 1280x720` / `Listening on 127.0.0.1:8764`

**Tests:**
1. Supported camera plugged in → detected (see `Found camera`).
2. Env override adds an entry:
   ```
   set PUSHNAV_CAMERA_IDS=aaaa:bbbb
   camera_server.exe
   ```
   → allowlist shows 4 entries incl. `AAAA:BBBB  user-configured`.
3. **Not-found diagnostic:** with a non-built-in camera connected and no override,
   confirm it exits with `No allowlisted camera found. ... USB video devices seen:`
   listing that camera's vid:pid.
4. **Decisive** (if you have a non-built-in camera, e.g. Arducam): confirm it is NOT
   found by default, then re-run with `PUSHNAV_CAMERA_IDS=<its vid:pid>` and confirm it
   IS found and streams.

**Scrutinize:** `parse_devpath_ids()` pulls VID/PID out of the DirectShow `DevicePath`.
Verify the printed `(XXXX:XXXX)` matches the device's real IDs
(Device Manager → Details → Hardware Ids).

---

## macOS — `camera/mac/Sources/CameraServer/*.swift`

**Build:** `cd camera/mac && swift build`  (or `scripts/build_camera_mac.sh` for release + copy)
**Run:** `.build/debug/camera_server`  (release script copies to `camera/mac/camera_server`)
- Grant the terminal **Camera permission** if macOS prompts.
- Make sure the **PushNav app is NOT running** (only one process can hold the camera).

### ✅ VERIFIED on macOS (2026-06-20, Apple Swift 6.1.2, arm64)

Built clean — but first `rm -rf .build` to clear a stale module cache that still
pointed at the repo's old path (`stargazingbuddy-evf` → `pushnav`); without that,
`swift build` fails with "PCH was compiled with module cache path …" / "missing
required module 'SwiftShims'". All checks pass:

- **Decimal `modelID` confirmed** — the openaicam reports
  `UVC Camera VendorID_13030 ProductID_37457` (= 0x32E6/0x9251). The new decimal
  branch matched it; the `openaicam` name fallback was never reached.
- **UVC control works** — exposure (1…5000) and gain (0…63) probed; auto-exposure
  forced OFF confirmed; capture session started; TCP listening on :8764.
- **Env override** — add (`aaaa:bbbb` → 4th `user-configured` entry), dedup
  (`0c45:6366` not re-added), malformed (`zzz` skipped, valid kept): all correct.
- **Decisive non-built-in test** — openaicam unplugged, only a **Kreo Owl Camera**
  (`VendorID_3141 ProductID_25453` = 0x0C45/0x636D, name is NOT `openaicam`)
  connected. Default allowlist → NOT found (`FATAL: No allowlisted camera found`).
  With `PUSHNAV_CAMERA_IDS=0c45:636d` → found purely by VID/PID, via BOTH the
  AVFoundation discovery (`Found camera: Kreo Owl Camera`) and the IOKit UVC path
  (`UVC control interface: user-configured … (VID=0x0C45, PID=0x636D)`), exposure/
  gain probed. This is the path that "could not be tested without a Mac" — it passes.

(Aside, pre-existing / out of scope: both cameras on hand advertise only YUV
`420v`/`yuvs`, no MJPEG, so they use the CIContext JPEG fallback.)

**Expect:**
- `Camera allowlist (N entries):` block
- `UVC control interface: <label> (VID=0x..., PID=0x...)`
- `Found camera: <name> [<modelID>]` — **copy this `modelID` string verbatim**
- capture starts; exposure/gain adjustable

### ✅ CONFIRMED (was the key unverified part of macOS): the `modelID` encoding

`CaptureManager.findCamera()` matches the capture device by `AVCaptureDevice.modelID`.

**Why this is suspect.** The *original* code matched `modelID.contains("0x9251")` — i.e.
it assumed the PID appears as the **hex** string `0x9251`. But macOS reports VID/PID in
`modelID` in **decimal**, e.g.:

```
UVC Camera VendorID_13030 ProductID_37457
```

…which is just the hex IDs converted:

| Hex | Decimal in modelID |
|-----|--------------------|
| `0x32E6` (VID) | `13030` |
| `0x9251` (PID) | `37457` |

So `"0x9251"` never appears, and that hex branch was effectively **dead code** — the
original app only ever found the camera via the *name* match (`localizedName` contains
`openaicam`), which hid the broken hex check. New cameras (Arducam/DECXIN) are NOT named
`openaicam`, so they can only be matched by VID/PID — which is why this must work.

The rewrite (`modelID(_:matches:)`) now tries **both** encodings (decimal
`VendorID_… ProductID_…` and hex `0x…`), keeping the `openaicam` name as a last fallback.
This was the one assumption that could not be tested without a Mac.

**Confirmed 2026-06-20:** macOS reports **decimal** (`VendorID_13030 ProductID_37457`),
the decimal branch matched the openaicam, and a non-`openaicam` Kreo Owl camera was
found purely by VID/PID — so the matcher is right. See the ✅ VERIFIED block above.

**What to verify:**
- **Report the exact `modelID` string** from the `Found camera:` line (confirms decimal vs hex).
- **Decisive test:** use a non-built-in camera (Arducam/DECXIN) whose `localizedName` does
  NOT contain `openaicam` — it can only be found via modelID matching. If found → VID/PID
  matching works. If NOT found → the encoding assumption is wrong and
  `findCamera()` / `modelID(_:matches:)` needs fixing to the real format you reported.
- Confirm `UVCController.find(in:)` succeeded (the `UVC control interface` line) and that
  exposure/gain actually change — that IOKit path needs the exact VID/PID match.

---

## Optional full-app / config test (both OSes)

Add to the app `config.json` under `"camera"`:
```json
"extra_camera_ids": ["vid:pid"]
```
- Windows: `%APPDATA%\ElectronicViewfinder\config.json`
- macOS: `~/Library/Application Support/ElectronicViewfinder/config.json`

Launch the app; the engine log should show `Passing PUSHNAV_CAMERA_IDS=... to camera server`.

---

## Report back / how to land fixes

- Build succeeded? (paste any warnings/errors)
- The startup allowlist block + the `Found camera` line (macOS: the full `modelID` string)
- Results of the env-override, not-found, and (if possible) non-built-in-camera tests
- **Any code changes:** commit them onto this branch (`camera-allowlist`) and push — they
  append cleanly. **Do not open a PR** (testing continues on the other machine first).
