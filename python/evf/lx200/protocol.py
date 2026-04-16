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
