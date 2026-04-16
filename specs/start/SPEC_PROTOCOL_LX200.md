# SPEC_PROTOCOL_LX200.md — PushNav

Version: 1.0
Status: Draft — not yet implemented
Date: 2026-04-16
Transport: TCP (default bind `0.0.0.0` so mobile apps on the LAN can reach it)
Default Port: 4030 (SkyFi-compatible; picked up by SkySafari auto-detect)
Direction: PushNav acts as TCP **server**; clients (SkySafari, Stellarium Mobile, INDI `indi_lx200basic`, ASCOM "Meade Generic") connect as **clients**

---

## 1. Overview

PushNav speaks a minimal subset of the Meade **LX200 Classic** serial command set over TCP. The same byte stream unlocks four ecosystems without a custom driver on any of them:

| Client | How it connects |
|--------|----------------|
| SkySafari Plus/Pro (iOS, Android, macOS, Windows) | Native "Meade LX-200" scope type over WiFi TCP |
| Stellarium Mobile PLUS (iOS, Android) | Native LX200/NexStar TCP, protocol auto-detected |
| INDI → KStars/Ekos, CCDCiel, PHD2, …        | Desktop runs `indi_lx200basic` pointed at our host:port |
| ASCOM → N.I.N.A., SharpCap, TheSkyX, APT, … | Desktop runs the "Meade Generic" ASCOM driver in TCP mode |

Because the same protocol serves all four, this spec is the *only* external-control spec we add; the existing binary Stellarium protocol (SPEC_PROTOCOL_STELLARIUM.md) continues to run in parallel on its own port.

### 1.1 One-way data flow rule

**Pointing state is owned by PushNav; third-party clients cannot mutate it.**

PushNav performs its own internal body-frame calibration (wizard Sync step → `config.sync_d_body`) and reports the *corrected* pointing outward. Any command from a client that looks like a sync/align/calibrate is treated as informational only — never as state input. Specifically:

- `:CM#` (SkySafari "Align") — reply the canonical "Coordinates matched" string, **do nothing else**. No writes to `config.sync_d_body`, no change to `PointingState`, no re-derivation of `finder_rotation`.
- `:Sr` / `:Sd` / `:MS#` (goto target) — store in `GotoTarget` for on-screen navigation guidance only. Never modifies pointing; push-to has no motor.

This matches the behavior of the existing Stellarium binary protocol: incoming GOTOs are advisory, outgoing position is authoritative.

Just like the Stellarium server, this server is **read-mostly from the client's perspective**: we report pointing, we accept and log goto targets, we never command a motor, and we never accept sync input.

---

## 2. Wire Format

LX200 is ASCII. Commands from the client are framed as `:<cmd>#` (leading colon, trailing hash). Responses are:

- **Fixed-width ASCII** terminated by `#` for getters (`:GR#`, `:GD#`, `:GVP#`, …)
- **A single ASCII digit with no terminator** for target-set acknowledgments (`:Sr`, `:Sd`, `:MS`) — `1` = accepted, `0` = rejected (for `:MS#`, `0` = slew started, `1<msg>#` = objection)
- **Nothing at all** for fire-and-forget commands (`:Q#`, `:U#`, unknown commands)

There is no length prefix, no checksum, no keep-alive. The socket stays open; the client polls `:GR#`/`:GD#` at 1–5 Hz.

Serial defaults (irrelevant for TCP but quoted by drivers on connect): 9600 baud, 8-N-1, no flow control.

---

## 3. Supported Commands

Minimum set required by all four client families. Unsupported commands are **silently consumed** (no reply) — this is important for the Meade Generic ASCOM driver, which probes with `:ED#` and other commands that the Classic never answered.

### 3.1 Getters

| Command | Response (high-precision, default) | Response (low-precision) |
|---------|-----------------------------------|--------------------------|
| `:GR#` | `HH:MM:SS#` | `HH:MM.T#` |
| `:GD#` | `sDD*MM:SS#` | `sDD*MM#` |
| `:GVP#` | `LX200 Classic#` *(identity — used for auto-detect)* | — |
| `:GVN#` | `PushNav 1.0#` *(firmware string)* | — |
| `:GVD#` | build date string, e.g. `Apr 16 2026#` | — |
| `:GVT#` | build time string, e.g. `12:34:56#` | — |

Precision mode: start in **high-precision** (HH:MM:SS / sDD*MM:SS). `:U#` toggles. Track per-connection.

### 3.2 Target setters (used for goto)

| Command | Argument | Response |
|---------|----------|----------|
| `:Sr HH:MM:SS#` or `:Sr HH:MM.T#` | Target RA | `1` accepted, `0` malformed |
| `:Sd sDD*MM:SS#` or `:Sd sDD*MM#` | Target Dec | `1` accepted, `0` malformed |
| `:MS#` | Slew to stored target | `0` = slew started (we always return `0`; push-to mount is the operator) |
| `:CM#` | Sync to stored target | `Coordinates matched.        #` *(29-byte reply; matches the Meade reference implementation; SkySafari accepts variable-length padding)* |
| `:Q#` | Stop slew / abort | (no response) |

On `:MS#` we treat the stored (RA, Dec) exactly like a Stellarium binary GOTO: write to `GotoTarget`, play the ack sound, log at INFO.

`:CM#` is **informational only** — per §1.1 the one-way data flow rule prohibits third-party state input. Reply the canonical string, log at INFO, do nothing else.

### 3.3 Tolerated but ignored (reply nothing)

`:U#` (toggle precision), `:RG#` `:RC#` `:RM#` `:RS#` (slew rate), `:Me#` `:Mw#` `:Mn#` `:Ms#` (move), `:Qe#` etc. (stop), `:ED#`, `:$BDG#`, everything else. No reply, no log spam above DEBUG.

---

## 4. Coordinate Formats

### 4.1 Right Ascension

High-precision: `HH:MM:SS#`
- Example: `05:47:12#`
- Range: `00:00:00` .. `23:59:59`

Low-precision: `HH:MM.T#` (T = tenths of a minute)
- Example: `05:47.2#`
- Range: `00:00.0` .. `23:59.9`

### 4.2 Declination

High-precision: `sDD*MM:SS#` (`*` is the literal Meade degree marker, byte `0x2A`)
- Example: `+45*59:07#` or `-23*26:15#`
- Range: `-90*00:00` .. `+90*00:00`

Low-precision: `sDD*MM#`
- Example: `+45*59#`
- Range: `-90*00` .. `+90*00`

### 4.3 Epoch — critical

SkySafari and most LX200 clients expect **JNow** (equator-of-date, IAU 2006 precession), *not* J2000. This is [fixed by the protocol and not configurable in SkySafari](https://support.simulationcurriculum.com/hc/en-us/community/posts/4901342475287).

`PointingState` stores **J2000** (the tetra3 solver output — our internal canonical form; proper motion has already been propagated to the DB build year by tetra3, so the J2000-frame coordinates already correspond to today's sky). The LX200 server must:
- Precess J2000 → JNow before formatting `:GR#`/`:GD#` responses
- Precess JNow → J2000 after parsing `:Sr`/`:Sd` target input, before storing into `GotoTarget`

Nutation and annual aberration are **not** applied — SkySafari and other LX200 clients expect "mean equinox of date" (precession only), not "true equinox of date" or "apparent place." Applying nutation would introduce a ~20″ systematic mismatch against SkySafari's expectation.

Add JNow helpers on `PointingSnapshot` / `GotoTarget` so all three protocols (current Stellarium binary, LX200, future Alpaca) share one epoch-conversion path.

Stellarium binary (existing) stays on J2000 — do not break SPEC_PROTOCOL_STELLARIUM.md.

#### Library choice: pyerfa

Precession is implemented using [**pyerfa**](https://github.com/liberfa/pyerfa) (the Python binding to liberfa, the open-source fork of IAU SOFA). Specifically `erfa.pmat06()`, the IAU 2006 Capitaine precession matrix.

Rationale over alternatives:
- vs. astropy — pyerfa is ~5 MB with numpy as only runtime dep; astropy is ~100 MB with lazy loading, auto-downloaded IERS tables, and a fight to bundle cleanly with Nuitka. We'd use 0.1% of astropy's surface area.
- vs. pure-Python Meeus ch. 21 — viable fallback, but owning the math for something this standardized is not worth the auditability cost.
- vs. skyfield — designed for ephemeris work (loads JPL .bsp files), wrong shape for a pure frame rotation.

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    ...existing...,
    "pyerfa>=2.0.0",
]
```

pyerfa ships manylinux/macOS/Windows wheels — no compilation needed on end-user machines, no IERS data files to manage, Nuitka-friendly (plain C extension).

#### Caching

The precession matrix changes by microarcseconds over 60-second intervals. The LX200 server should cache the current J2000→JNow matrix and regenerate it at most once per minute (cheap guard; pyerfa calls are already sub-millisecond, but caching removes any worry about worst-case per-poll overhead on embedded hardware).

---

## 5. Python Encoding Examples

### 5.1 Precession (pyerfa)

Place in `python/evf/engine/epoch.py` — shared by LX200 now, Alpaca later.

```python
"""J2000 <-> JNow precession using pyerfa (IAU 2006)."""

import threading
import time

import erfa
import numpy as np


_MJD_J2000 = 51544.5  # Modified Julian Date of J2000.0 TT

# Cache the precession matrix for _MATRIX_CACHE_SECONDS; regeneration is cheap
# but this removes any worst-case per-poll overhead.
_MATRIX_CACHE_SECONDS = 60.0
_cache_lock = threading.Lock()
_cached_matrix: np.ndarray | None = None
_cached_at: float = 0.0
_cached_inv: np.ndarray | None = None


def _unix_to_mjd_tt(unix_seconds: float) -> float:
    """Unix time (UTC) -> MJD(TT). Ignores leap-second subtlety at ~30s level
    — irrelevant for arc-minute push-to. For <1" precision, use erfa.utctai."""
    return 40587.0 + unix_seconds / 86400.0 + 32.184 / 86400.0 + 37.0 / 86400.0


def _current_matrix() -> tuple[np.ndarray, np.ndarray]:
    """Return (P, P_inv) where P rotates J2000 -> mean equinox of date."""
    global _cached_matrix, _cached_at, _cached_inv
    now = time.time()
    with _cache_lock:
        if _cached_matrix is None or (now - _cached_at) > _MATRIX_CACHE_SECONDS:
            mjd_tt = _unix_to_mjd_tt(now)
            # erfa.pmat06 returns the IAU 2006 precession matrix
            P = erfa.pmat06(2400000.5, mjd_tt)
            _cached_matrix = P
            _cached_inv = P.T   # rotation matrix: inverse == transpose
            _cached_at = now
        return _cached_matrix, _cached_inv


def _radec_to_vec(ra_deg: float, dec_deg: float) -> np.ndarray:
    ra = np.deg2rad(ra_deg)
    dec = np.deg2rad(dec_deg)
    return np.array([
        np.cos(dec) * np.cos(ra),
        np.cos(dec) * np.sin(ra),
        np.sin(dec),
    ])


def _vec_to_radec(v: np.ndarray) -> tuple[float, float]:
    ra = np.rad2deg(np.arctan2(v[1], v[0])) % 360.0
    dec = np.rad2deg(np.arcsin(v[2]))
    return ra, dec


def j2000_to_jnow(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    """J2000 (ICRS) -> mean equinox of date. Returns (ra_deg, dec_deg)."""
    P, _ = _current_matrix()
    return _vec_to_radec(P @ _radec_to_vec(ra_deg, dec_deg))


def jnow_to_j2000(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    """Mean equinox of date -> J2000 (ICRS). Returns (ra_deg, dec_deg)."""
    _, P_inv = _current_matrix()
    return _vec_to_radec(P_inv @ _radec_to_vec(ra_deg, dec_deg))
```

### 5.2 LX200 formatting

```python
def format_ra_hi(ra_hours: float) -> bytes:
    """Format JNow RA as HH:MM:SS# (high precision)."""
    total_seconds = int(round(ra_hours * 3600)) % 86400
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}#".encode("ascii")


def format_dec_hi(dec_degrees: float) -> bytes:
    """Format JNow Dec as sDD*MM:SS# (high precision)."""
    sign = "+" if dec_degrees >= 0 else "-"
    d = abs(dec_degrees)
    deg = int(d)
    m_float = (d - deg) * 60.0
    minutes = int(m_float)
    seconds = int(round((m_float - minutes) * 60.0))
    if seconds == 60:
        seconds = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        deg += 1
    return f"{sign}{deg:02d}*{minutes:02d}:{seconds:02d}#".encode("ascii")


def parse_ra_hms(arg: str) -> float:
    """Parse 'HH:MM:SS' or 'HH:MM.T' -> hours."""
    if "." in arg:                    # HH:MM.T low precision
        h, mt = arg.split(":", 1)
        return int(h) + float(mt) / 60.0
    h, m, s = arg.split(":")
    return int(h) + int(m) / 60.0 + int(s) / 3600.0


def parse_dec_dms(arg: str) -> float:
    """Parse 'sDD*MM:SS' or 'sDD*MM' -> degrees."""
    sign = -1.0 if arg[0] == "-" else 1.0
    body = arg.lstrip("+-").replace("*", ":")
    parts = body.split(":")
    d = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return sign * (d + m / 60.0 + s / 3600.0)
```

---

## 6. Server Behavior

### 6.1 Startup

1. Bind TCP server to `0.0.0.0:4030` (configurable via ConfigManager; bind host configurable too — default `0.0.0.0` for LAN reach so phones can connect).
2. Listen for connections (allow multiple clients — SkySafari and KStars can be attached simultaneously).
3. Server starts at app launch regardless of tracking state (same lifecycle as `StellariumServer`).

### 6.2 Per-client read loop

A single server thread (like `StellariumServer._run`) uses `select` to fan in all client sockets. For each client:

1. Read available bytes into a per-client buffer.
2. Scan for `#`-terminated tokens (or reply-less shortcuts like bare `:Q`).
3. Dispatch each command; buffer stragglers for the next read.
4. Per-client state: `{precision: "hi"|"lo", pending_ra, pending_dec}`.

### 6.3 Command dispatch

```
:GR#  →  snap = pointing.read()
         if not snap.valid: reply "00:00:00#"  (some drivers hate silence on :GR#)
         else:
           ra_jnow_deg, _ = epoch.j2000_to_jnow(snap.ra_j2000, snap.dec_j2000)
           reply format_ra_hi(ra_jnow_deg / 15.0)
:GD#  →  snap = pointing.read()
         _, dec_jnow_deg = epoch.j2000_to_jnow(snap.ra_j2000, snap.dec_j2000)
         reply format_dec_hi(dec_jnow_deg)
:Sr X → parse X (JNow) into pending_ra_jnow; reply "1" (or "0" on parse error)
:Sd X → parse X (JNow) into pending_dec_jnow; reply "1"
:MS#  → if pending_ra_jnow and pending_dec_jnow are set:
          ra_j2000_deg, dec_j2000_deg = epoch.jnow_to_j2000(
              pending_ra_jnow * 15.0, pending_dec_jnow)
          goto_target.set(ra_j2000_deg, dec_j2000_deg)  # same as Stellarium path
          play_ack()
          log INFO "LX200 GOTO received: ..."
          optionally kick off stellarium_object lookup (share code path with StellariumServer._fetch_goto_details)
        reply "0"   (always — push-to has no motor; we never reject)
:CM#  → reply "Coordinates matched.        #" (32 chars + #)
        log INFO "LX200 :CM# received (informational, no state change)"
        # Per §1.1: one-way data flow; no calibration writes, no PointingState updates
:Q#   → clear pending_ra / pending_dec; no reply
        (does NOT clear GotoTarget — aborting a pending slew does not
         erase an already-committed navigation target)
:U#   → toggle this client's precision mode; no reply
:GVP# → reply "LX200 Classic#"
:GVN# → reply "PushNav <app version from VERSION.json>#"
unknown :XX# → consume, no reply, log DEBUG
```

### 6.4 Broadcast? No.

Unlike the Stellarium binary protocol there is **no periodic push**. Clients poll. Respond only to received commands; never send unsolicited bytes (SkySafari and the ASCOM driver both get confused by unexpected bytes).

### 6.5 Client disconnects / errors

Same as Stellarium server: remove from client list, close socket, log INFO. Never crash the thread. Handle `ConnectionResetError`, `BrokenPipeError`, `OSError`.

### 6.6 Shutdown

1. Close all client sockets.
2. Close server socket.
3. Occurs during app graceful shutdown (see SPEC_ARCHITECTURE.md).

---

## 7. Code Layout

New package, mirroring the Stellarium one, plus one shared engine-level helper for epoch conversion:

```
python/evf/engine/
  epoch.py           # pyerfa-backed J2000 <-> JNow helpers (shared by LX200 + future Alpaca)

python/evf/lx200/
  __init__.py
  protocol.py        # parse_ra_hms, parse_dec_dms, format_ra_hi, format_dec_hi, dispatch table
  server.py          # Lx200Server — select-based TCP loop, multi-client, per-client state
```

New runtime dependency in `pyproject.toml`: `pyerfa>=2.0.0`.

Engine wiring in `python/evf/engine/engine.py`:

```python
from evf.lx200.server import Lx200Server

class Engine:
    def __init__(self, ...):
        ...
        self._lx200: Lx200Server | None = None

    def startup_lx200(self) -> None:
        try:
            self._lx200 = Lx200Server(self._pointing_state, goto_target=self._goto_target)
            self._lx200.start()
        except Exception as exc:
            logger.error("Failed to start LX200 server: %s", exc)
            self._lx200 = None

    def shutdown(self):
        ...
        if self._lx200:
            self._lx200.stop()
```

Called from the same startup sequence that currently calls `startup_stellarium`. Disable/enable from config.

Shared helper (new): `python/evf/engine/pointing.py` gains `PointingSnapshot.ra_jnow`, `dec_jnow` properties and `GotoTarget.set_jnow(...)`, so LX200 and a future Alpaca endpoint don't each re-implement precession.

---

## 8. Client Configuration

### 8.1 SkySafari Plus/Pro
- Settings → Telescope → Setup
- Scope Type: **Meade LX-200 GPS** (or **LX-200 Classic** — either works)
- Mount Type: **Equatorial Push-To** (or **Alt-Az Push-To** if the user is set up that way)
- Connection: **WiFi**, "Use WiFi-to-Serial adapter or TCP/IP" → **Direct TCP/IP**
- IP = PushNav host; Port = **4030**
- "Auto-Detect SkyFi" may also find us if we answer the SkyFi discovery UDP broadcast on port 4031 — **optional**, add in a later revision if demand warrants.

### 8.2 Stellarium Mobile PLUS
- Menu → Observing Tools → Telescope → Add
- Connection: **Network (TCP)**; IP = PushNav host; Port = **4030**
- Protocol: leave on auto-detect; answering `:GVP#` with `LX200 Classic` is enough.

### 8.3 INDI (KStars / Ekos, CCDCiel, PHD2)
On the desktop:
```
indiserver -v indi_lx200basic
```
In KStars → Ekos → Profile Editor → Mount: **LX200 Basic**. Then in the driver's Connection tab: **TCP**, Host = PushNav host, Port = 4030.

### 8.4 ASCOM (Windows — N.I.N.A., SharpCap, TheSkyX, APT)
- Install [ASCOM Platform 6.6+](https://ascom-standards.org/) and the Meade LX200 driver.
- Chooser → **Meade Generic** (preferred) or **Meade Classic and Autostar I**.
- Properties → COM Port → set to the driver's **TCP mode**; Host = PushNav host, Port = 4030.
- If the connection hangs on the `:ED#` probe, tick **"Do not bypass Intro prompts"** in the newer Meade Generic (v1.3.9.482+) — or rely on §3.3 (we silently consume `:ED#`).

### 8.5 ASCOM Alpaca (future)
Out of scope for v1 of this spec. A native Alpaca `ITelescopeV3` HTTP endpoint using `alpyca` would eliminate the Windows-only ASCOM shim; revisit after the LX200 path is validated in the field.

---

## 9. Interaction with Existing Specs

- **SPEC_PROTOCOL_STELLARIUM.md** — unchanged. The binary Stellarium server continues on its own port (10001). Both servers can run simultaneously.
- **SPEC_ARCHITECTURE.md** — add `Lx200Server` next to `StellariumSrv` in the Core Engine box.
- **SPEC_PRODUCT.md** — LX200 support is an additive external-control feature; no UI wizard changes required. A single toggle in config ("Enable LX200 server / port") is sufficient.
- **ACCEPTANCE_TESTS.md** — add cases per §10.

---

## 10. Acceptance Tests

End-to-end, pointed at a known target (tests/samples/ + goto targets):

1. **SkySafari position** — with tracking locked, SkySafari crosshair follows PushNav's pointing within ≤1 poll (≤2 s). RA/Dec in SkySafari match PushNav's on-screen RA/Dec within 1 arcmin.
2. **SkySafari goto** — right-click an object in SkySafari → GoTo. PushNav logs `LX200 GOTO received: RA=…h Dec=…°`, `GotoTarget` is set, ack sound plays, navigation guidance chevrons appear.
3. **Stellarium Mobile PLUS position** — same check as (1) on iOS or Android.
4. **INDI / KStars** — `indi_lx200basic` connects; KStars' Sky Map shows the telescope crosshair at PushNav's pointing; crosshair updates at the INDI poll rate (default 1 Hz).
5. **ASCOM / N.I.N.A.** — "Meade Generic" connects via TCP; N.I.N.A.'s mount tab shows RA/Dec matching PushNav.
6. **Silent ignore** — sending `:ED#` (or any other unsupported command) does not break the session; the next `:GR#` still returns the current position.
7. **Multi-client** — SkySafari *and* KStars attached at once; both see consistent position; goto from either is logged and stored.
8. **Unit tests** — round-trip `format_ra_hi(parse_ra_hms(x)) == x` across the full range; malformed `:Sr BAD#` replies `0`; epoch conversion round-trip (`jnow_to_j2000(j2000_to_jnow(x))`) is symmetric to <1 mas; cross-check `j2000_to_jnow` against an independent source (e.g. astropy in the test env only, not in the shipped bundle) for a handful of stars at a fixed epoch — agreement within 1″.
9. **Nuitka bundling** — `pyerfa` is included in the standalone build on all three platforms; `import erfa` succeeds in the packaged `.app` / Linux binary / Windows exe.

---

## 11. Non-Goals

- Mount motion control — PushNav is push-to; we always reply `0` to `:MS#` and never emit step pulses.
- Sync / alignment input from clients — per §1.1, `:CM#` and any sync-like command is acknowledge-only. PushNav's calibration is owned internally (wizard Sync step).
- Focuser, rotator, filter wheel commands — out of scope.
- LX200 GPS-only commands (`:GG#`, `:Gg#`, etc. site/lat/long queries) — consume silently; a future revision may proxy these to the Stellarium Remote Control observer data we already fetch.
- SkyFi UDP auto-discovery (port 4031) — optional future enhancement.
- ASCOM Alpaca HTTP endpoint — separate future spec.
