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

"""Camera binary protocol — message envelope and type constants.

Per SPEC_PROTOCOL_CAMERA.md §3:
  Every message: type (u32 LE) | length (u32 LE) | payload (length bytes)
"""

import json
import logging
import struct

logger = logging.getLogger(__name__)

# Header: type (u32) + length (u32) = 8 bytes
_HEADER_FMT = "<II"
_HEADER_SIZE = 8

# -- Message types (camera → app) -------------------------------------------
MSG_HELLO = 0x00
MSG_FRAME = 0x01
MSG_CONTROL_INFO = 0x02
MSG_ERROR = 0x03

# -- Message types (app → camera) -------------------------------------------
MSG_SET_CONTROL = 0x11
MSG_GET_CONTROLS = 0x12

_TYPE_NAMES = {
    MSG_HELLO: "HELLO",
    MSG_FRAME: "FRAME",
    MSG_CONTROL_INFO: "CONTROL_INFO",
    MSG_ERROR: "ERROR",
    MSG_SET_CONTROL: "SET_CONTROL",
    MSG_GET_CONTROLS: "GET_CONTROLS",
}


class DisconnectError(Exception):
    """Raised when the remote end closes the connection mid-message."""


def encode_message(msg_type: int, payload: bytes = b"") -> bytes:
    """Encode a protocol message with header + payload."""
    header = struct.pack(_HEADER_FMT, msg_type, len(payload))
    return header + payload


def encode_json_message(msg_type: int, obj: dict) -> bytes:
    """Encode a protocol message with a JSON payload."""
    return encode_message(msg_type, json.dumps(obj).encode("utf-8"))


def _recv_exact(sock, n: int) -> bytes:
    """Read exactly n bytes from sock. Raises DisconnectError on short read."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise DisconnectError("Connection closed")
        buf.extend(chunk)
    return bytes(buf)


def read_message(sock) -> tuple[int, bytes]:
    """Read one message from the socket.

    Returns:
        (msg_type, payload) tuple.

    Raises:
        DisconnectError: If the connection closes mid-message.
    """
    header = _recv_exact(sock, _HEADER_SIZE)
    msg_type, length = struct.unpack(_HEADER_FMT, header)
    payload = _recv_exact(sock, length) if length > 0 else b""
    return msg_type, payload


def type_name(msg_type: int) -> str:
    return _TYPE_NAMES.get(msg_type, f"UNKNOWN(0x{msg_type:02x})")
