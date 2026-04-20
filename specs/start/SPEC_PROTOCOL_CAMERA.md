# SPEC_PROTOCOL_CAMERA.md — PushNav

Document version: 2.1
Protocol version (wire): **1** — must match `data/VERSION.json.protocol_version`
and `PROTOCOL_VERSION` in `python/evf/camera/client.py`, `camera/mac/Sources/.../main.swift`, and the Linux/Windows camera servers.
Status: Reflects Current Implementation
Date: 2026-04-20
Transport: TCP on localhost
Applies to: macOS (Swift), Linux (C/V4L2), Windows (C/DirectShow)

The document-revision number above (2.1) is editorial — it tracks updates to
this spec file, not the wire protocol. The wire protocol is unchanged since
v1 of the project.

---

## 1. Goals

- Provide a platform-agnostic contract between Python app and native camera backend.
- Stream MJPEG frames (no transcoding required in Python).
- Expose only required controls for v1: Exposure + Gain.
- Enable robust disconnect detection and allow auto-restart.

### Non-goals (v1)
- Camera selection / multiple cameras
- Changing resolution/fps
- Generic UVC descriptor-driven control exposure in UI
- Overlays / in-app crosshair

---

## 2. Transport

- Camera server binds to `127.0.0.1`.
- Default port: `8764`.
- Python app connects as a TCP client at startup.
- Camera server may be spawned by Python or run standalone for debugging.

---

## 3. Message Envelope

Every message uses the same envelope:

- `type`   : 4 bytes unsigned int, little-endian
- `length` : 4 bytes unsigned int, little-endian
- `payload`: `length` bytes

```
+---------+----------+------------------+
| type    | length   | payload          |
| u32 LE  | u32 LE   | length bytes     |
+---------+----------+------------------+
```

Rules:
- `length` may be 0.
- Receiver must read exactly 8 bytes header, then exactly `length` payload bytes.
- If socket closes mid-message, treat as disconnect.
- Unknown `type` MUST be ignored (log at DEBUG) unless in handshake stage.
  This preserves forward compatibility when a newer client sends messages
  an older server doesn't recognize.

> **Known issue (not yet fixed):** the macOS Swift backend
> (`camera/mac/Sources/CameraServer/TCPServer.swift` in the `parseHeader`
> path) currently **disconnects** on unknown message types instead of
> ignoring them, violating the rule above. This breaks forward-compat for
> any future message added to the protocol. Linux/Windows C backends fall
> through their if/else dispatch chain without disconnecting, which matches
> the spec. A follow-up task should change the Swift branch to log-and-skip
> the frame rather than tear the connection down. Tracked separately; do
> not rely on "ignore unknown" from macOS until that fix lands.

---

## 4. Protocol Versioning + Handshake (Required)

Even in v1, a handshake is REQUIRED to prevent silent breakage later.

### 4.1 Message Type: HELLO (0x00)

Direction: both ways  
Payload: UTF-8 JSON object

**Camera → App**: sent immediately after client connects.  
**App → Camera**: client responds once after receiving camera HELLO.

Example payload:

```json
{
  "protocol_version": 1,
  "backend": "mac-swift",
  "backend_version": "0.1.0",
  "camera_model": "openaicam",
  "stream_format": "MJPEG",
  "default_width": 1280,
  "default_height": 720,
  "default_fps": 30
}
```

The `camera_model` value is backend-specific:
- macOS (Swift) sends the hardcoded string `"openaicam"`.
- Linux (V4L2) and Windows (DirectShow) send the probed device model string.

Clients should treat `camera_model` as free-form informational and not parse
it as an enum.

Handshake rules:
- If `protocol_version` mismatch:
  - App logs error (INFO)
  - App enters ERROR state (or SETUP with error banner)
  - App closes socket
  - Camera server may exit
- After HELLO exchange, camera server MUST send CONTROL_INFO.

---

## 5. Message Types

### 5.1 Camera → App

#### 0x01 FRAME
Payload: raw JPEG bytes (a single MJPEG frame)

Rules:
- FRAME messages may be sent continuously at camera FPS.
- No metadata required in payload v1.
- Python stores only the latest frame; older frames are overwritten.
- If app is not ready (e.g., still in SETUP), frames are still allowed.

#### 0x02 CONTROL_INFO
Payload: UTF-8 JSON object

Required schema (v1):

```json
{
  "controls": [
    {
      "id": "exposure",
      "label": "Exposure",
      "type": "int",
      "min": 1,
      "max": 5000,
      "step": 1,
      "cur": 100,
      "unit": "100us"
    },
    {
      "id": "gain",
      "label": "Gain",
      "type": "int",
      "min": 0,
      "max": 255,
      "step": 1,
      "cur": 10,
      "unit": "raw"
    }
  ]
}
```

Rules:
- CONTROL_INFO MUST be sent once right after handshake completes.
- CONTROL_INFO MUST be re-sent after every SET_CONTROL, so the app sees the
  actual applied value (which may differ from the requested value if the
  camera clamped or rounded it). Backends currently re-send unconditionally
  on every SET_CONTROL — a superset of the spec requirement that simplifies
  implementation and gives the UI a consistent update cadence.
- App builds UI controls dynamically from this list.

#### 0x03 ERROR
Payload: UTF-8 string

Rules:
- Backend should send ERROR on:
  - camera not found
  - permission failure
  - UVC control failures that prevent operation
  - capture session failure
- Fatal errors should be followed by server closing connection (and likely exiting).

---

### 5.2 App → Camera

#### 0x11 SET_CONTROL
Payload: UTF-8 JSON object

Schema:

```json
{
  "id": "exposure",
  "value": 250
}
```

Rules:
- `id` must be `"exposure"` or `"gain"` in v1.
- Backend clamps to valid range.
- Backend applies change as quickly as possible.
- Backend MUST respond with CONTROL_INFO reflecting applied values.

#### 0x12 GET_CONTROLS
Payload: empty

Rules:
- Backend responds with CONTROL_INFO immediately.

---

## 6. Required Backend Behavior (v1)

### 6.1 Force Auto Exposure OFF at initialization
Camera backend MUST force auto exposure OFF during initialization, before streaming begins.
This setting is NOT exposed in UI.

The macOS Swift backend implements this via a direct USB control request
through IOKit (the `UVCController` class in `camera/mac/Sources/CameraServer/`),
because AVFoundation does not expose UVC auto-exposure controls. Linux and
Windows backends use their native V4L2 / DirectShow APIs.

### 6.2 Single supported camera model
Backend assumes one supported camera model (known VID/PID + known control layout).
If not found:
- Send ERROR with descriptive message
- Exit process (Python will restart with retry policy)

### 6.3 Stream format and encoding
- MJPEG frames are forwarded as-is (no re-encoding) if capture provides JPEG.
- If capture provides raw frames, backend must encode JPEG.
- Protocol payload for FRAME is always JPEG bytes in v1.

---

## 7. Disconnect Semantics

- No explicit keepalive in v1.
- Liveness is based on: socket connected + frames arriving.
- If the app does not receive frames for `_FRAME_STALL_TIMEOUT` seconds it
  treats the camera as stalled and triggers a subprocess restart. Currently
  hardcoded to **2.0 seconds** in `python/evf/camera/subprocess_mgr.py`; no
  config hook. If the timeout needs to be user-tunable later, add a config
  field rather than a command-line flag (so it persists across runs).

---

## 8. Test Vectors (Required)

A simple Python test client must be able to:
1. Connect
2. Receive HELLO
3. Send HELLO
4. Receive CONTROL_INFO
5. Receive FRAME bytes continuously
6. Send SET_CONTROL and observe CONTROL_INFO update

This enables backend development independent of the full UI.

---

## 9. Reserved Extensions (Do not use in v1)

Reserved message types:
- 0x13 START_STREAM
- 0x14 STOP_STREAM
- 0x15 SET_STREAM_CONFIG
- 0x16 GET_LATEST_FRAME
- 0x20 STATS

---

## 10. macOS Implementation Notes (Reference Only)

The macOS Swift backend lives in `camera/mac/Sources/CameraServer/` and is
built via Swift Package Manager (see `scripts/build_camera_mac.sh`).

Key classes in the backend:

- `UVCController` — performs UVC control reads/writes via IOKit USB control
  requests. Used specifically for auto-exposure-off and for the exposure /
  gain set paths that AVFoundation cannot reach.
- `CaptureSession` wrapper — AVFoundation capture session + sample-buffer
  delegate; emits MJPEG-compressed `Data` into the TCP FRAME payload.
- `TCPServer` — single-client TCP server that accepts the Python app and
  handles the length-prefixed framing. **Known issue:** currently disconnects
  on unknown message types in `parseHeader`; should instead skip and continue
  (see §3).
