# LX200 Protocol Server — Implementation Design

Date: 2026-04-16
Branch: `lx200`
Related protocol spec: `specs/start/SPEC_PROTOCOL_LX200.md`
Status: Approved, ready for implementation plan

---

## Context

The protocol spec (`SPEC_PROTOCOL_LX200.md`) establishes *what* wire format PushNav
will speak to third-party clients. This design document establishes *how* we
implement it in the codebase: module boundaries, data flow, test strategy, and
engine wiring.

### One-way data flow rule (governing principle)

PushNav owns its pointing state. Third-party clients receive the corrected
pointing (JNow) and send advisory goto targets. They cannot sync, calibrate,
or otherwise mutate PushNav's internal state. `:CM#` is acknowledge-only.

### Scope for first PR

Full spec in a single PR: LX200 server + `pyerfa` dep + engine wiring + tests.
`:CM#` is implemented as acknowledge-only per the one-way data flow rule.
Hardcoded defaults (`0.0.0.0:4030`, always on) — no config toggle for now.

---

## Architecture

### Module layout

```
python/evf/engine/epoch.py          (NEW)  — pyerfa-backed J2000↔JNow, cached matrix
python/evf/lx200/__init__.py        (NEW)  — empty
python/evf/lx200/protocol.py        (NEW)  — formatters, parsers, Lx200ClientState,
                                              Lx200Context, dispatch()
python/evf/lx200/server.py          (NEW)  — Lx200Server: select-loop, multi-client
python/evf/engine/engine.py         (EDIT) — startup_lx200() mirrors startup_stellarium()
pyproject.toml                      (EDIT) — add pyerfa>=2.0.0
scripts/build_mac.sh                (EDIT) — --include-package=erfa
scripts/build_linux.sh              (EDIT) — --include-package=erfa
scripts/build_windows.bat           (EDIT) — --include-package=erfa
```

### Module contracts

**`epoch.py`** — pure functions, no sockets, no threading in the API:
```python
j2000_to_jnow(ra_deg, dec_deg) -> (ra_deg, dec_deg)
jnow_to_j2000(ra_deg, dec_deg) -> (ra_deg, dec_deg)
```
Internal: `threading.Lock` around a 60-second-cached `erfa.pmat06` matrix
and its transpose. IAU 2006 Capitaine precession; no nutation, no aberration
(matches SkySafari "mean equinox of date").

**`lx200/protocol.py`** — pure functions plus two dataclasses:
- `Lx200ClientState` — per-socket: `precision_hi`, `pending_ra_jnow_hours`, `pending_dec_jnow_deg`, `recv_buffer`
- `Lx200Context` — engine handles: `pointing`, `goto_target`, `play_ack`, `app_version`
- Formatters: `format_ra_hi/lo`, `format_dec_hi/lo`
- Parsers: `parse_ra_hms`, `parse_dec_dms`
- `dispatch(cmd: bytes, state, ctx) -> bytes | None` — single entry point, command table

**`lx200/server.py`** — `Lx200Server` class:
- Socket plumbing only — select loop, accept, per-client buffer, RST recovery
- Per-client state stored as `dict[socket, Lx200ClientState]`
- Delegates every complete command (`#`-terminated token) to `protocol.dispatch()`
- Never emits unsolicited bytes
- Constructor: `Lx200Server(pointing, host="0.0.0.0", port=4030, goto_target=None, app_version="0.0.0")` — engine passes the real version string read from `data/VERSION.json`; the `"0.0.0"` default exists only so tests can construct the server without plumbing version metadata

### Key invariants

1. **One token in, at most one reply out.** Never emit unsolicited bytes.
2. **PointingState is always read J2000.** Precession happens inside `protocol.py`, via `epoch.py`.
3. **GotoTarget is always written J2000.** LX200 is the only place JNow exists.
4. **Per-client state is isolated.** Two clients can send targets concurrently without interference.
5. **`protocol.py` never touches sockets.** `server.py` never formats RA/Dec.

---

## Data flow

### Outbound query (`:GR#`)

```
Client → server (recv 1024) → buffer → scan for '#' → token b":GR"
       → dispatch(b":GR", state, ctx)
       → ctx.pointing.read()   # J2000 snapshot
       → epoch.j2000_to_jnow(ra, dec)   # → JNow
       → format_ra_hi(ra_jnow_deg / 15)  # → b"HH:MM:SS#"
       → client.sendall(reply)
```

`:GD#`, `:GVP#`, `:GVN#` follow the same shape.

### Inbound goto (`:Sr` → `:Sd` → `:MS#`)

```
:Sr 05:47:12#   → state.pending_ra_jnow_hours = 5.7867; reply b"1"
:Sd +45*59:07#  → state.pending_dec_jnow_deg  = 45.985;  reply b"1"
:MS#            → if pending both set:
                    ra_j2000, dec_j2000 = epoch.jnow_to_j2000(...)
                    ctx.goto_target.set(ra_j2000, dec_j2000)
                    ctx.play_ack(); log INFO
                  reply b"0"
                  (or b"1<no target set>#" if targets missing)
```

### `:CM#` (informational only)

```
log INFO "LX200 :CM# received (informational, no state change)"
reply b"Coordinates matched.        #"
# NO writes to pointing/config/goto — per one-way data flow rule
```

### Unknown (`:ED#`, etc.) and `:Q#`

- Unknown: consume, log DEBUG, no reply.
- `:Q#`: clear pending target, no reply.
- `:U#`: flip `state.precision_hi`, no reply.

---

## Epoch module

```python
# python/evf/engine/epoch.py
import threading, time
import erfa
import numpy as np

_CACHE_SECONDS = 60.0
_lock = threading.Lock()
_cached_matrix: np.ndarray | None = None
_cached_transpose: np.ndarray | None = None
_cached_at: float = 0.0


def _unix_to_jd_tt(unix_seconds: float) -> tuple[float, float]:
    """Unix UTC → two-part JD(TT). UTC→TT offset ≈ 69.184 s (as of 2026);
    error ≤1 s contributes ~15 mas precession error — negligible."""
    return 2440587.5, unix_seconds / 86400.0 + 69.184 / 86400.0


def _refresh_matrix() -> tuple[np.ndarray, np.ndarray]:
    global _cached_matrix, _cached_transpose, _cached_at
    now = time.time()
    with _lock:
        if _cached_matrix is None or (now - _cached_at) > _CACHE_SECONDS:
            jd1, jd2 = _unix_to_jd_tt(now)
            P = erfa.pmat06(jd1, jd2)
            _cached_matrix = P
            _cached_transpose = P.T
            _cached_at = now
        return _cached_matrix, _cached_transpose


def _radec_to_vec(ra_deg, dec_deg):
    ra, dec = np.deg2rad(ra_deg), np.deg2rad(dec_deg)
    cd = np.cos(dec)
    return np.array([cd * np.cos(ra), cd * np.sin(ra), np.sin(dec)])


def _vec_to_radec(v):
    ra = np.rad2deg(np.arctan2(v[1], v[0])) % 360.0
    dec = np.rad2deg(np.arcsin(np.clip(v[2], -1.0, 1.0)))
    return ra, dec


def j2000_to_jnow(ra_deg, dec_deg):
    P, _ = _refresh_matrix()
    return _vec_to_radec(P @ _radec_to_vec(ra_deg, dec_deg))


def jnow_to_j2000(ra_deg, dec_deg):
    _, Pt = _refresh_matrix()
    return _vec_to_radec(Pt @ _radec_to_vec(ra_deg, dec_deg))
```

---

## Protocol module (sketch — full code in implementation plan)

```python
# python/evf/lx200/protocol.py — key surface

@dataclass
class Lx200ClientState:
    precision_hi: bool = True
    pending_ra_jnow_hours: float | None = None
    pending_dec_jnow_deg: float | None = None
    recv_buffer: bytes = b""


@dataclass
class Lx200Context:
    pointing: PointingState
    goto_target: GotoTarget | None
    play_ack: Callable[[], None]
    app_version: str


def format_ra_hi(ra_hours: float) -> bytes: ...
def format_ra_lo(ra_hours: float) -> bytes: ...
def format_dec_hi(dec_deg: float) -> bytes: ...
def format_dec_lo(dec_deg: float) -> bytes: ...
def parse_ra_hms(arg: str) -> float: ...
def parse_dec_dms(arg: str) -> float: ...


def dispatch(cmd: bytes, state: Lx200ClientState, ctx: Lx200Context) -> bytes | None:
    # Command table:
    #   :GR  → format_ra_hi/lo of epoch.j2000_to_jnow(pointing.read())
    #   :GD  → format_dec_hi/lo of epoch.j2000_to_jnow(pointing.read())
    #   :GVP → b"LX200 Classic#"
    #   :GVN → b"PushNav <version>#"
    #   :Sr  → parse → state.pending_ra_jnow_hours, reply b"1"/b"0"
    #   :Sd  → parse → state.pending_dec_jnow_deg, reply b"1"/b"0"
    #   :MS  → if pending both: convert → goto_target.set, play_ack, reply b"0"
    #          else reply b"1<no target set>#"
    #   :CM  → log, reply canonical string, NO state change
    #   :Q   → clear pending, no reply
    #   :U   → flip precision, no reply
    #   else → DEBUG log, no reply
```

---

## Server module (sketch — full code in implementation plan)

```python
# python/evf/lx200/server.py — key surface

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 4030
_SELECT_POLL_INTERVAL = 0.1
_MAX_RECV_BUFFER = 4096


class Lx200Server:
    def __init__(self, pointing, host=_DEFAULT_HOST, port=_DEFAULT_PORT,
                 goto_target=None, app_version="0.0.0"): ...
    def start(self) -> None: ...
    def stop(self, timeout=2.0) -> None: ...

    # Internal: _run (select loop), _accept_new_client, _handle_client_data,
    # _remove_client, _cleanup.
    #
    # _handle_client_data:
    #   - recv, append to state.recv_buffer
    #   - if buffer > _MAX_RECV_BUFFER: trim oldest half, log WARNING
    #   - while b"#" in buffer:
    #       cmd, _, rest = buffer.partition(b"#")
    #       cmd = cmd.lstrip(noise bytes)
    #       reply = dispatch(cmd, state, ctx)  # exceptions caught
    #       if reply: client.sendall(reply)
```

### Differences from StellariumServer

| Aspect | StellariumServer | Lx200Server |
|--------|------------------|-------------|
| Bind host | `127.0.0.1` | `0.0.0.0` |
| Port | 10001 | 4030 |
| Model | Push-broadcast at 1 Hz | Pure request/response |
| Framing | Fixed binary (24/20 B) | ASCII, `#`-terminated |
| Per-client state | None | `Lx200ClientState` |
| Clients stored as | list | dict `{socket: state}` |
| Select timeout | broadcast interval | 100 ms |
| Unsolicited bytes | Yes | **Never** |

---

## Engine wiring

```python
# python/evf/engine/engine.py
from evf.lx200.server import Lx200Server

class Engine:
    def __init__(self, ...):
        ...
        self._lx200: Lx200Server | None = None

    def startup_lx200(self) -> None:
        try:
            self._lx200 = Lx200Server(
                self._pointing_state,
                goto_target=self._goto_target,
                app_version=self._app_version,
            )
            self._lx200.start()
        except Exception as exc:
            logger.error("Failed to start LX200 server: %s", exc)
            self._lx200 = None

    def shutdown(self):
        ...
        if self._lx200 is not None:
            self._lx200.stop()
```

`startup_lx200()` called from the same startup sequence as `startup_stellarium()`.

App version read once at engine init from `data/VERSION.json` (via `evf.paths`)
and stored as `self._app_version`, so `:GVN#` returns a real version string.

---

## Test strategy

### `tests/test_epoch.py`
1. Round-trip symmetry (`jnow_to_j2000(j2000_to_jnow(x)) == x`) within 1 mas across
   a grid of (ra, dec).
2. Magnitude sanity — a J2000 star gets displaced by 0.2°–0.7° in 2026 (bounds test,
   no hard-coded reference).
3. Cache correctness — two calls within 60 s return the same cached matrix object.
4. Pole stability — `j2000_to_jnow(_, 89.26)` returns valid ranges (RA in [0, 360),
   dec in [−90, 90]).
5. Optional — if `astropy` importable in test env only (not shipped), cross-check
   against `SkyCoord(...).transform_to(FK5(equinox=Time.now()))` within 1″.

### `tests/test_lx200_protocol.py`
Exercises `dispatch()` with no sockets:

- **Formatters**: HH:MM:SS rollover, minus-zero Dec, +90/−90 boundaries, low-precision variants.
- **Parsers**: both precision formats, out-of-range raises ValueError.
- **Round-trip**: parse → format matches within 1″.
- **Dispatch** (fake PointingState + GotoTarget):
  - `:GR` with invalid pointing → `b"00:00:00#"`
  - `:GR` with known pointing → decodable, converts back through epoch within 1″
  - `:GVP` → `b"LX200 Classic#"`
  - `:GVN` → `b"PushNav 1.0.0#"`
  - `:Sr` / `:Sd` valid → `b"1"` + state populated
  - `:Sr BAD` → `b"0"`
  - `:MS` with pending → `b"0"`, goto_target set in J2000, play_ack called
  - `:MS` without pending → `b"1<no target set>#"`
  - `:CM` → canonical string, **and verify no writes to goto_target/pointing**
  - `:Q` → None, pending cleared
  - `:U` → None, precision flipped; next `:GR` uses low-precision
  - `:ED` → None, no error
  - malformed / empty → None

### `tests/test_lx200_server.py`
Integration with real sockets on ephemeral ports (`port=0`):

1. Start/stop round-trip.
2. Invalid-pointing `:GR#` returns sentinel.
3. Valid-pointing `:GR#`/`:GD#` decodes back through epoch within 1″.
4. Multi-client isolation — client A at low precision, client B at high.
5. Goto round-trip: `:Sr` + `:Sd` + `:MS#` sets GotoTarget in J2000 within 1″.
6. Malformed-recovery: mixed buffer with `:BAD` tokens still processes good ones.
7. Buffer overflow: 5000 bytes without `#` → WARNING, trim, server alive.
8. RST mid-write: `SO_LINGER {0,0}` force-close → server thread survives.
9. Clean shutdown within timeout.

### Manual smoke tests (checklist in implementation plan)
Per SPEC_PROTOCOL_LX200.md §10 items 1–5: SkySafari, Stellarium Mobile PLUS, KStars/INDI, N.I.N.A./ASCOM.

### Nuitka bundle test (SPEC §10 item 9)
Build on all three platforms, run the packaged binary, check log for
`LX200 server listening on 0.0.0.0:4030`. Implicit `import erfa` verification.

---

## Cross-cutting concerns

### Dependency
Add `pyerfa>=2.0.0` to `pyproject.toml` dependencies. Run `uv lock` to refresh
`uv.lock`. Manylinux / macOS / Windows wheels available on PyPI; no end-user
compilation.

### Nuitka
Add `--include-package=erfa` to `scripts/build_mac.sh`, `scripts/build_linux.sh`,
`scripts/build_windows.bat`.

### Firewall
Binding `0.0.0.0:4030` will trigger:
- macOS: Gatekeeper "allow incoming connections" dialog on first run of new build
  (same as existing webserver on 8080 — no code change).
- Linux: typically no prompt.
- Windows: Defender Firewall prompt on first run of the built `.exe`.

Mention in release notes.

### Logging
- INFO: server start/stop, client connect/disconnect, GOTO received (with JNow→J2000 shown), `:CM#` received.
- WARNING: recv buffer overflow.
- DEBUG: unknown command, parse failure.
- ERROR: dispatch exception (caught).

### Graceful degradation
- `pyerfa` import failure → log ERROR, don't start server, rest of app continues.
- Port in use → log ERROR, `_lx200 = None`, rest of app continues.
- Dispatch exception → caught, logged, client stays connected, no reply.

### Thread safety
- `PointingState.read()` / `GotoTarget.set()` — already thread-safe.
- `epoch.py` matrix cache — behind `threading.Lock`.
- `Lx200ClientState` / `_clients` dict — only touched by the server thread.
  No new cross-thread mutations.

### Documentation updates
- `specs/start/SPEC_ARCHITECTURE.md` §2 — add `Lx200Server` to the Core Engine box.
- `specs/start/ACCEPTANCE_TESTS.md` — new "L. LX200 Protocol" section referencing SPEC §10.
- `CLAUDE.md` — one-line mention of `pyerfa` in Key Dependencies.
- Release notes — LX200 support and port 4030 connection info.

---

## Out of scope (deferred)

- Config toggle / UI setting to disable the server — not in v1.
- ASCOM Alpaca native HTTP endpoint — separate future design.
- SkyFi UDP broadcast auto-discovery (port 4031) — may add if demand warrants.
- Multi-star sync via `:CM#` — explicitly prohibited by one-way data flow rule.
- Asyncio refactor of both servers — not this PR.

---

## Open risks

1. **UTC→TT offset drift** — we hardcode 69.184 s. If a new leap second is added
   post-2026 and we don't rebuild, precession gets a ~15 mas error (still well
   within arc-minute push-to precision). Document in `epoch.py`.
2. **Firewall prompts on macOS/Windows** — first-run UX surprise; mitigate via release notes.
3. **Port 4030 collision** — rare but possible; logged and handled gracefully.
4. **ASCOM Meade Generic `:ED#` probe** — handled by silently consuming unknown commands. Explicitly tested.
