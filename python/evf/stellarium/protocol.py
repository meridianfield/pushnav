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

"""Stellarium telescope binary protocol — encode/decode per SPEC_PROTOCOL_STELLARIUM.md."""

import struct
import time

# Position message: 24 bytes, little-endian
# <HHQIii  →  length(u16) type(u16) time_us(u64) ra(u32) dec(i32) status(i32)
_POSITION_FMT = "<HHQIii"
_POSITION_LEN = 24

# GOTO message from Stellarium: 20 bytes
# <HHQIi  →  length(u16) type(u16) time_us(u64) ra(u32) dec(i32)
_GOTO_FMT = "<HHQIi"
_GOTO_LEN = 20


def encode_position(ra_hours: float, dec_degrees: float) -> bytes:
    """Encode a 24-byte Stellarium telescope position message.

    Args:
        ra_hours:    Right Ascension in hours (0.0–24.0), J2000.
        dec_degrees: Declination in degrees (-90.0–+90.0), J2000.

    Returns:
        24-byte message ready to send over TCP.
    """
    timestamp_us = int(time.time() * 1_000_000)
    ra_uint32 = int(ra_hours * (2**32 / 24.0)) & 0xFFFFFFFF
    dec_int32 = max(-2**31, min(2**31 - 1, int(dec_degrees * (2**31 / 180.0))))
    return struct.pack(
        _POSITION_FMT,
        _POSITION_LEN,  # length
        0,              # type
        timestamp_us,
        ra_uint32,
        dec_int32,
        0,              # status OK
    )


def decode_goto(data: bytes) -> tuple[float, float]:
    """Decode a 20-byte Stellarium GOTO message (for logging only).

    Args:
        data: 20 bytes received from Stellarium.

    Returns:
        (ra_hours, dec_degrees) tuple.

    Raises:
        struct.error: If data is not exactly 20 bytes.
    """
    _length, _msg_type, _timestamp, ra_raw, dec_raw = struct.unpack(_GOTO_FMT, data)
    ra_hours = ra_raw * (24.0 / 2**32)
    dec_degrees = dec_raw * (180.0 / 2**31)
    return ra_hours, dec_degrees
