# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PushNav is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PushNav. If not, see <https://www.gnu.org/licenses/>.

"""LX200 Classic ASCII command parsing and dispatch.

Pure functions - no sockets, fully unit-testable.
See specs/start/SPEC_PROTOCOL_LX200.md for the full command table.
"""

# -- formatters --------------------------------------------------------------


def format_ra_hi(ra_hours: float) -> bytes:
    """Format RA as HH:MM:SS# (high precision). Input wraps mod 24."""
    total_seconds = int(round(ra_hours * 3600)) % 86400
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}#".encode("ascii")


def format_ra_lo(ra_hours: float) -> bytes:
    """Format RA as HH:MM.T# (low precision, tenths of a minute)."""
    total_tenths = int(round(ra_hours * 600)) % 14400
    h, rem = divmod(total_tenths, 600)
    m, t = divmod(rem, 10)
    return f"{h:02d}:{m:02d}.{t}#".encode("ascii")


def format_dec_hi(dec_deg: float) -> bytes:
    """Format Dec as sDD*MM:SS# (high precision)."""
    sign = "+" if dec_deg >= 0 else "-"
    d = abs(dec_deg)
    deg = int(d)
    m_f = (d - deg) * 60.0
    m = int(m_f)
    s = int(round((m_f - m) * 60.0))
    if s == 60:
        s, m = 0, m + 1
    if m == 60:
        m, deg = 0, deg + 1
    return f"{sign}{deg:02d}*{m:02d}:{s:02d}#".encode("ascii")


def format_dec_lo(dec_deg: float) -> bytes:
    """Format Dec as sDD*MM# (low precision)."""
    sign = "+" if dec_deg >= 0 else "-"
    d = abs(dec_deg)
    deg = int(d)
    m = int(round((d - deg) * 60.0))
    if m == 60:
        m, deg = 0, deg + 1
    return f"{sign}{deg:02d}*{m:02d}#".encode("ascii")


# -- parsers -----------------------------------------------------------------


def parse_ra_hms(arg: str) -> float:
    """Parse 'HH:MM:SS' or 'HH:MM.T' -> hours in [0, 24)."""
    arg = arg.strip()
    if "." in arg and ":" in arg and arg.index(".") > arg.index(":"):
        # HH:MM.T low precision form
        h, mt = arg.split(":", 1)
        return (int(h) + float(mt) / 60.0) % 24.0
    parts = arg.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return (h + m / 60.0 + s / 3600.0) % 24.0


def parse_dec_dms(arg: str) -> float:
    """Parse 'sDD*MM:SS' or 'sDD*MM' -> degrees in [-90, 90]."""
    arg = arg.strip()
    if not arg:
        raise ValueError("empty Dec")
    sign = -1.0 if arg[0] == "-" else 1.0
    # Some clients use various degree markers; normalize to ':'
    body = arg.lstrip("+-").replace("*", ":").replace("'", ":").replace("\u00b0", ":")
    parts = body.split(":")
    d = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    value = sign * (d + m / 60.0 + s / 3600.0)
    if not -90.0 <= value <= 90.0:
        raise ValueError(f"Dec out of range: {value}")
    return value


# -- types -------------------------------------------------------------------

import logging
from dataclasses import dataclass
from typing import Callable

from evf.engine.epoch import j2000_to_jnow, jnow_to_j2000
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState

logger = logging.getLogger(__name__)


@dataclass
class Lx200ClientState:
    """State attached to each LX200 TCP client connection."""

    precision_hi: bool = True
    pending_ra_jnow_hours: float | None = None
    pending_dec_jnow_deg: float | None = None
    recv_buffer: bytes = b""


@dataclass
class Lx200Context:
    """Engine handles passed into dispatch."""

    pointing: PointingState
    goto_target: GotoTarget | None
    play_ack: Callable[[], None]
    app_version: str


# -- dispatch ----------------------------------------------------------------

# SkySafari tolerates variable-length padding here; 29 bytes matches the
# Meade reference implementation's canonical reply.
_CM_REPLY = b"Coordinates matched.        #"


def dispatch(cmd: bytes, state: Lx200ClientState, ctx: Lx200Context) -> bytes | None:
    """Dispatch one complete LX200 command. Returns reply bytes or None.

    `cmd` is a complete command WITHOUT the trailing '#' (server strips it).
    Example inputs: b":GR", b":Sr 05:47:12", b":U", b":Q".
    """
    if not cmd.startswith(b":"):
        logger.debug("LX200 malformed (no leading :): %r", cmd)
        return None

    body = cmd[1:].decode("ascii", errors="replace")

    # --- getters ---
    if body == "GR":
        return _reply_get_ra(state, ctx)
    if body == "GD":
        return _reply_get_dec(state, ctx)
    if body == "GVP":
        return b"LX200 Classic#"
    if body == "GVN":
        return f"PushNav {ctx.app_version}#".encode("ascii")

    # --- target setters ---
    if body.startswith("Sr"):
        return _handle_set_ra(body[2:], state)
    if body.startswith("Sd"):
        return _handle_set_dec(body[2:], state)

    # --- actions ---
    if body == "MS":
        return _handle_move_slew(state, ctx)
    if body == "CM":
        # Per SPEC_PROTOCOL_LX200.md §1.1: informational only, no state change.
        logger.info("LX200 :CM# received (informational, no state change)")
        return _CM_REPLY
    if body == "Q":
        state.pending_ra_jnow_hours = None
        state.pending_dec_jnow_deg = None
        return None

    # --- toggles ---
    if body == "U":
        state.precision_hi = not state.precision_hi
        return None

    # --- unknown: consume silently (important for ASCOM Meade Generic :ED# probe) ---
    logger.debug("LX200 ignored command: %r", cmd)
    return None


def _reply_get_ra(state: Lx200ClientState, ctx: Lx200Context) -> bytes:
    snap = ctx.pointing.read()
    if not snap.valid:
        return b"00:00:00#" if state.precision_hi else b"00:00.0#"
    ra_jnow_deg, _ = j2000_to_jnow(snap.ra_j2000, snap.dec_j2000)
    ra_hours = ra_jnow_deg / 15.0
    return format_ra_hi(ra_hours) if state.precision_hi else format_ra_lo(ra_hours)


def _reply_get_dec(state: Lx200ClientState, ctx: Lx200Context) -> bytes:
    snap = ctx.pointing.read()
    if not snap.valid:
        return b"+00*00:00#" if state.precision_hi else b"+00*00#"
    _, dec_jnow_deg = j2000_to_jnow(snap.ra_j2000, snap.dec_j2000)
    return format_dec_hi(dec_jnow_deg) if state.precision_hi else format_dec_lo(dec_jnow_deg)


def _handle_set_ra(arg: str, state: Lx200ClientState) -> bytes:
    try:
        state.pending_ra_jnow_hours = parse_ra_hms(arg)
        return b"1"
    except (ValueError, IndexError):
        logger.debug("LX200 :Sr parse failed: %r", arg)
        state.pending_ra_jnow_hours = None
        return b"0"


def _handle_set_dec(arg: str, state: Lx200ClientState) -> bytes:
    try:
        state.pending_dec_jnow_deg = parse_dec_dms(arg)
        return b"1"
    except (ValueError, IndexError):
        logger.debug("LX200 :Sd parse failed: %r", arg)
        state.pending_dec_jnow_deg = None
        return b"0"


def _handle_move_slew(state: Lx200ClientState, ctx: Lx200Context) -> bytes:
    if state.pending_ra_jnow_hours is None or state.pending_dec_jnow_deg is None:
        return b"1<no target set>#"
    ra_jnow_deg = state.pending_ra_jnow_hours * 15.0
    ra_j2000, dec_j2000 = jnow_to_j2000(ra_jnow_deg, state.pending_dec_jnow_deg)
    # GotoTarget.set() plays the ack sound internally — we do not call play_ack
    # separately to avoid a double-play. ctx.play_ack exists for future hooks.
    if ctx.goto_target is not None:
        ctx.goto_target.set(ra_j2000, dec_j2000)
    logger.info(
        "LX200 GOTO: (JNow) RA=%.4fh Dec=%.4f° -> (J2000) RA=%.4f° Dec=%.4f°",
        state.pending_ra_jnow_hours,
        state.pending_dec_jnow_deg,
        ra_j2000,
        dec_j2000,
    )
    return b"0"
