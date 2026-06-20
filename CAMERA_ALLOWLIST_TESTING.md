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
"supply the camera only via env, with its built-in entry removed" path. **Windows and
macOS were written carefully but not yet compiled or run** — that's what this note covers.

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

**Expect:**
- `Camera allowlist (N entries):` block
- `UVC control interface: <label> (VID=0x..., PID=0x...)`
- `Found camera: <name> [<modelID>]` — **copy this `modelID` string verbatim**
- capture starts; exposure/gain adjustable

### ⚠️ Key unverified part (macOS)

`CaptureManager.findCamera()` matches the capture device by `AVCaptureDevice.modelID`.
We don't know whether macOS reports VID/PID in that string as **decimal**
(`VendorID_13030 ProductID_37457`) or **hex** (`0x32e6`); the code tries **both**, with
the legacy name match (`openaicam`) as a fallback.

- **Report the exact `modelID` string** from the `Found camera:` line.
- **Decisive macOS test:** use a non-built-in camera (Arducam/DECXIN) whose
  `localizedName` does NOT contain `openaicam` — it can only be found via modelID
  matching. If found → VID/PID matching works. If NOT found → the modelID encoding
  assumption is wrong, and `findCamera()` / `modelID(_:matches:)` needs fixing to the
  real format.
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
