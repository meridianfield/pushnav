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
macOS section). **Windows is now also fully verified** (2026-06-20, MSVC 14.50 / VS 18
Community / x64 — see the ✅ block in the Windows section), including real MJPEG
streaming from a Waveshare OV9281 and the decisive non-built-in-by-VID/PID path.
All three platforms are now verified.

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

### ✅ VERIFIED on Windows (2026-06-20, MSVC 14.50.35717 / VS 18 Community, x64)

Compiled clean with `cl /W4 /O2` — **zero warnings** (first compile of this file),
no code changes needed. Tested against a real **Waveshare OV9281** (`openaicam`,
`32E6:9251`) plus the laptop's non-allowlisted **Integrated Camera** (`30C9:0030`).
All checks pass:

- **Built-in match (real hardware)** — with no env override, the built-in `32E6:9251`
  matched the Waveshare: `Found camera 'openaicam' (32E6:9251)`. This is the core fix.
- **Real MJPEG streaming** — unlike macOS/AVFoundation (where this same camera offered
  only YUV), DirectShow exposes MJPEG: `Using MJPEG capture 1280x720`. A TCP client
  pulled **30 valid JPEG frames** (~25 KB each, SOI `FFD8` / EOI `FFD9`, no trailing pad)
  via the direct passthrough path — no libjpeg needed.
- **Handshake + controls** — HELLO/CONTROL_INFO exchanged; `probe_controls()` reported
  exposure `[-13..-1]` and gain `[0..63]`. `SET_CONTROL` applied exactly: exposure
  -5→-13, gain 0→63 (server echoed the new `cur` in CONTROL_INFO).
- **Env override** — `aaaa:bbbb` → 4th `user-configured` entry; `0c45:6366` deduped
  against the built-in; malformed `zzz` skipped with the warning. All correct.
- **Not-found diagnostic** — with only the Integrated Camera connected, exits via
  `return 1` with `No allowlisted camera found` +
  `USB video devices seen:  30c9:0030  Integrated Camera`.
- **Decisive non-built-in test** — the Integrated Camera (`30C9:0030`, whose name is
  NOT `openaicam` / any OV9281) is NOT found by default, then found **purely by VID/PID**
  with `PUSHNAV_CAMERA_IDS=30c9:0030` (`Found camera 'Integrated Camera' (30C9:0030)` →
  capture graph running → listening). This is the path that "could not be tested without
  the hardware" — it passes. `parse_devpath_ids()` returned the correct IDs for both
  cameras.

**Build note (this dev box):** the VS dev shell already had `INCLUDE`/`LIB` set with
`cl.exe` on PATH, but `NoDefaultCurrentDirectoryInExePath=1` is in effect, so a bare
`build.bat` is "not recognized" — run it as `.\build.bat`, or invoke `cl.exe` directly
(`cl /W4 /O2 /Fe:camera_server.exe camera_server.c ws2_32.lib ole32.lib oleaut32.lib strmiids.lib uuid.lib`).

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

**✅ VERIFIED (2026-06-20, Windows):** the config→env→native chain was confirmed by driving
the real `ConfigManager` + `SubprocessManager._build_env()` and launching the actual
`camera_server.exe` with the env it produced. A config of `"extra_camera_ids": ["30c9:0030"]`
loaded, forwarded as `PUSHNAV_CAMERA_IDS=30c9:0030`, and the native server matched it:
`Found camera 'Integrated Camera' (30C9:0030)`. Also confirmed: the default-merge preserves
the user's list (other camera keys fall back to defaults); multiple entries and stray
whitespace normalize to a comma-separated `vid:pid` string; an empty list makes `_build_env`
return `None` (inherit parent env); a config entry composes with any pre-existing
`PUSHNAV_CAMERA_IDS`; malformed entries are forwarded and skipped by the native parser. This
is shared Python (manager.py + subprocess_mgr.py), so it applies to all three OSes.

> ⚠️ **The config file must keep `"version": 1`.** `ConfigManager` discards the whole file and
> reverts to defaults on any version mismatch (manager.py:75), silently dropping
> `extra_camera_ids`. Editing the app-generated `config.json` (which already carries the
> version) is fine; hand-creating a versionless file is not.

---

## Report back / how to land fixes

- Build succeeded? (paste any warnings/errors)
- The startup allowlist block + the `Found camera` line (macOS: the full `modelID` string)
- Results of the env-override, not-found, and (if possible) non-built-in-camera tests
- **Any code changes:** commit them onto this branch (`camera-allowlist`) and push — they
  append cleanly. **Do not open a PR** (testing continues on the other machine first).
