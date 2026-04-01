# SPEC_PROTOCOL_STELLARIUM.md — PushNav

Version: 2.0
Status: Reflects Current Implementation
Date: 2026-02-19
Transport: TCP on localhost
Default Port: 10001
Direction: App acts as TCP **server**; Stellarium connects as **client**

---

## 1. Overview

PushNav broadcasts its current pointing position to Stellarium using the **Stellarium Telescope Control** binary protocol. This enables a real-time crosshair overlay in Stellarium showing where the camera is pointed.

Stellarium's "External software or a remote computer" telescope type connects to our TCP server and expects periodic position updates.

Incoming GOTO commands are decoded and stored for navigation guidance.

---

## 2. Message Format

All messages are **24 bytes**, little-endian.

```
Offset  Size   Type     Field       Description
------  -----  -------  ----------  ------------------------------------
0       2      uint16   length      Message length in bytes (always 24)
2       2      uint16   type        Message type (always 0)
4       8      uint64   time        Microseconds since 1970-01-01 UTC
12      4      uint32   ra          Right Ascension (encoded, unsigned)
16      4      int32    dec         Declination (encoded, signed)
20      4      int32    status      0 = OK, <0 = error
```

struct.pack format string: `<HHQIii`

- `H` = uint16 (length)
- `H` = uint16 (type)
- `Q` = uint64 (timestamp)
- `I` = uint32 (RA, unsigned)
- `i` = int32 (Dec, signed)
- `i` = int32 (status)

---

## 3. RA/Dec Encoding

### 3.1 Right Ascension

RA is encoded as an unsigned 32-bit integer spanning the full 0–24 hour range:

```
ra_uint32 = int(ra_hours * (2**32 / 24.0)) & 0xFFFFFFFF
```

Scale: `0x80000000` (2,147,483,648) = 12 hours. Full circle `0x100000000` = 24 hours.

### 3.2 Declination

Dec is encoded as a signed 32-bit integer. The implementation uses:

```
dec_int32 = max(-2**31, min(2**31 - 1, int(dec_degrees * (2**31 / 180.0))))
```

The value is clamped to the int32 range.

---

## 4. Python Encoding Example

```python
import struct
import time

def encode_position(ra_hours: float, dec_degrees: float) -> bytes:
    """Encode a 24-byte Stellarium telescope position message.

    Args:
        ra_hours:    Right Ascension in hours (0.0 to 24.0), J2000
        dec_degrees: Declination in degrees (-90.0 to +90.0), J2000

    Returns:
        24-byte message ready to send over TCP.
    """
    msg_length = 24
    msg_type = 0
    timestamp_us = int(time.time() * 1_000_000)
    ra_uint32 = int(ra_hours * (2**32 / 24.0)) & 0xFFFFFFFF
    dec_int32 = max(-2**31, min(2**31 - 1, int(dec_degrees * (2**31 / 180.0))))
    status = 0

    return struct.pack('<HHQIii',
        msg_length, msg_type, timestamp_us,
        ra_uint32, dec_int32, status)
```

---

## 5. Decoding Incoming Messages (GOTO)

Stellarium sends GOTO commands as 20-byte messages (`length=20`, no status field).
GOTO commands are decoded and stored in a `GotoTarget` for navigation guidance.

```python
def decode_goto(data: bytes) -> tuple[float, float]:
    """Decode a Stellarium GOTO message.

    Args:
        data: 20 bytes received from Stellarium.

    Returns:
        (ra_hours, dec_degrees) tuple.
    """
    length, msg_type, timestamp, ra_raw, dec_raw = struct.unpack('<HHQIi', data)
    ra_hours = ra_raw * (24.0 / 2**32)
    dec_degrees = dec_raw * (180.0 / 2**31)
    return ra_hours, dec_degrees
```

GOTO handling:
- Decoded RA (hours) is converted to degrees: `ra_deg = ra_hours * 15.0`
- Stored in `GotoTarget` for navigation guidance display
- Acknowledgment sound plays on receipt
- Object info fetched from Stellarium Remote Control API (port 8090)
- Never attempt mount control
- Never change PointingState from a GOTO

---

## 6. Connection Lifecycle

### 6.1 Server startup

1. Bind TCP server to `127.0.0.1:10001`.
2. Listen for connections (allow multiple clients).
3. Server starts at app launch regardless of tracking state.

### 6.2 Client connects (Stellarium)

1. Accept connection, log at INFO.
2. Play acknowledgment sound.
3. Fetch observer status from Stellarium Remote Control API (best-effort).
4. Begin sending position updates at ~1 Hz interval.
5. If PointingState is not yet valid, do NOT send messages (wait for first solve).

### 6.3 Broadcast loop

```
every 1 second:
    if PointingState.valid:
        ra_hours = ra_j2000_degrees / 15.0
        msg = encode_position(ra_hours, dec_degrees)
        for each connected client:
            try send(msg)
            on error: close client, log at INFO
```

### 6.4 Client disconnects

1. Remove from client list.
2. Log at INFO.
3. No state change — server continues accepting new connections.

### 6.5 Server shutdown

1. Close all client sockets.
2. Close server socket.
3. Occurs during app graceful shutdown (see SPEC_ARCHITECTURE.md).

---

## 7. Stellarium Configuration

To connect Stellarium to PushNav:

1. Open Stellarium → Configuration → Plugins → Telescope Control.
2. Enable plugin, restart Stellarium if needed.
3. Add telescope: type "External software or a remote computer".
4. Host: `localhost`, Port: `10001`.
5. Connect.

The telescope crosshair should appear and update at ~1 Hz while the app is TRACKING.

For navigation guidance, also enable the Stellarium Remote Control plugin (port 8090).

---

## 8. Error Handling

- If no valid PointingState exists, send nothing (do not send stale or zero coordinates).
- If a client socket errors on send, close that client silently (log at INFO).
- Socket errors must never crash the Stellarium thread or affect the solver.
- The server thread must handle `ConnectionResetError`, `BrokenPipeError`, and `OSError` gracefully.
