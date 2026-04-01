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

"""Camera TCP client — connects to the camera server subprocess.

Per SPEC_PROTOCOL_CAMERA.md §4–5 and SPEC_ARCHITECTURE.md §4.1/§7.
"""

import json
import logging
import socket
import threading
import time

from evf.camera.protocol import (
    MSG_CONTROL_INFO,
    MSG_ERROR,
    MSG_FRAME,
    MSG_GET_CONTROLS,
    MSG_HELLO,
    MSG_SET_CONTROL,
    DisconnectError,
    encode_json_message,
    encode_message,
    read_message,
    type_name,
)
from evf.engine.frame_buffer import LatestFrame

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8764


class ProtocolError(Exception):
    """Raised on handshake or protocol version mismatch."""


class CameraClient:
    """TCP client that speaks the camera binary protocol.

    Connects, performs the HELLO handshake, receives CONTROL_INFO,
    then continuously receives FRAME messages into a LatestFrame buffer.
    """

    def __init__(
        self,
        frame_buffer: LatestFrame,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
    ) -> None:
        self._frame_buffer = frame_buffer
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frame_id = 0
        self._controls: list[dict] = []
        self._controls_lock = threading.Lock()
        self._hello_info: dict = {}
        self._on_controls_cb: callable | None = None
        self._on_error_cb: callable | None = None
        self._last_frame_time: float = 0.0
        self._connected = False

    # -- public API -----------------------------------------------------------

    def connect(self, timeout: float = 5.0) -> dict:
        """Connect and perform handshake. Returns the camera HELLO info dict.

        Raises:
            ProtocolError: On version mismatch or handshake failure.
            ConnectionRefusedError: If the server is not running.
            DisconnectError: If the connection drops during handshake.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect((self._host, self._port))
        logger.info("Connected to camera server at %s:%d", self._host, self._port)

        # Receive camera HELLO
        msg_type, payload = read_message(self._sock)
        if msg_type != MSG_HELLO:
            raise ProtocolError(f"Expected HELLO, got {type_name(msg_type)}")
        self._hello_info = json.loads(payload.decode("utf-8"))
        logger.info("Camera HELLO: %s", self._hello_info)

        # Validate protocol version
        cam_version = self._hello_info.get("protocol_version")
        if cam_version != PROTOCOL_VERSION:
            raise ProtocolError(
                f"Protocol version mismatch: camera={cam_version}, expected={PROTOCOL_VERSION}"
            )

        # Send our HELLO response
        our_hello = {"protocol_version": PROTOCOL_VERSION, "app": "evf", "app_version": "0.1.0"}
        self._sock.sendall(encode_json_message(MSG_HELLO, our_hello))
        logger.debug("Sent HELLO response")

        # Receive CONTROL_INFO
        msg_type, payload = read_message(self._sock)
        if msg_type != MSG_CONTROL_INFO:
            raise ProtocolError(f"Expected CONTROL_INFO, got {type_name(msg_type)}")
        self._update_controls(payload)

        self._connected = True
        return self._hello_info

    def start_receiving(self) -> None:
        """Start the background frame-receiving thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._recv_loop, name="camera-recv", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop receiving and close the connection."""
        self._stop_event.set()
        self._connected = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        logger.info("Camera client stopped")

    def set_control(self, control_id: str, value: int) -> None:
        """Send a SET_CONTROL message."""
        if self._sock is None:
            return
        msg = encode_json_message(MSG_SET_CONTROL, {"id": control_id, "value": value})
        try:
            self._sock.sendall(msg)
        except OSError as exc:
            logger.error("Failed to send SET_CONTROL: %s", exc)

    def get_controls(self) -> None:
        """Send a GET_CONTROLS request."""
        if self._sock is None:
            return
        try:
            self._sock.sendall(encode_message(MSG_GET_CONTROLS))
            logger.debug("Sent GET_CONTROLS")
        except OSError as exc:
            logger.error("Failed to send GET_CONTROLS: %s", exc)

    @property
    def controls(self) -> list[dict]:
        with self._controls_lock:
            return list(self._controls)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_frame_time(self) -> float:
        return self._last_frame_time

    def on_controls_update(self, callback: callable) -> None:
        """Register a callback for CONTROL_INFO updates."""
        self._on_controls_cb = callback

    def on_error(self, callback: callable) -> None:
        """Register a callback for ERROR messages."""
        self._on_error_cb = callback

    # -- internal -------------------------------------------------------------

    def _recv_loop(self) -> None:
        assert self._sock is not None
        try:
            while not self._stop_event.is_set():
                try:
                    msg_type, payload = read_message(self._sock)
                except socket.timeout:
                    continue
                self._handle_message(msg_type, payload)
        except (DisconnectError, ConnectionResetError, BrokenPipeError, OSError) as exc:
            if not self._stop_event.is_set():
                logger.warning("Camera connection lost: %s", exc)
                self._connected = False

    def _handle_message(self, msg_type: int, payload: bytes) -> None:
        if msg_type == MSG_FRAME:
            self._frame_id += 1
            self._last_frame_time = time.monotonic()
            self._frame_buffer.set(payload, self._last_frame_time, self._frame_id)
        elif msg_type == MSG_CONTROL_INFO:
            self._update_controls(payload)
        elif msg_type == MSG_ERROR:
            error_msg = payload.decode("utf-8", errors="replace")
            logger.error("Camera error: %s", error_msg)
            if self._on_error_cb:
                self._on_error_cb(error_msg)
        else:
            logger.debug("Ignoring unknown message type: %s", type_name(msg_type))

    def _update_controls(self, payload: bytes) -> None:
        try:
            data = json.loads(payload.decode("utf-8"))
            with self._controls_lock:
                self._controls = data.get("controls", [])
            logger.debug("CONTROL_INFO: %s", self._controls)
            if self._on_controls_cb:
                self._on_controls_cb(self._controls)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Bad CONTROL_INFO payload: %s", exc)
