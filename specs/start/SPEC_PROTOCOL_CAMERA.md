# SPEC_PROTOCOL_CAMERA.md — PushNav

Version: 2.0
Status: Reflects Current Implementation
Date: 2026-02-19
Transport: TCP on localhost
Applies to: macOS (Swift), Linux (C/V4L2), Windows (C/DirectShow)

Prototype references (keep these paths):
- macOS camera prototype: `~/Devel/Learning/webcam/camera_viewer.swift`
- UVC parsing prototype: `~/Devel/Learning/webcam/uvc_controls.swift`
- Enumeration helper: `~/Devel/Learning/webcam/webcam_probe.swift`
- macOS behavior notes: `~/Devel/Learning/webcam/how_openaicam.md`
- UVC generalization notes: `~/Devel/Learning/webcam/generalisation.md`

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
- Unknown `type` must be ignored (log at DEBUG) unless in handshake stage.

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
  "camera_model": "KNOWN_SINGLE_MODEL_V1",
  "stream_format": "MJPEG",
  "default_width": 1280,
  "default_height": 720,
  "default_fps": 30
}
```

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
- CONTROL_INFO MUST be re-sent if:
  - camera clamps a requested value
  - camera changes a value due to constraints (rare in v1)
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

macOS prototype reference:
- `~/Devel/Learning/webcam/camera_viewer.swift` (UVCController class)
- `~/Devel/Learning/webcam/how_openaicam.md` (why AVFoundation cannot change UVC controls directly)

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
- If app does not receive frames for N seconds (configurable; default 2s),
  it may treat the camera as stalled and restart.

Note: If implemented, ensure this does not trigger during expected temporary stalls.

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

Backend should be derived from `camera_viewer.swift` by stripping AppKit UI.

Key code sections to reuse (approximate):
- UVCController class (~lines 95–382)
- AVFoundation capture session (~lines 572–626)
- Frame capture delegate (~lines 628–631)
- SampleBuffer → image conversion (~lines 696–738), adapted to JPEG bytes.
