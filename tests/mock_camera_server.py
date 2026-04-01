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

"""Mock camera server — serves sample images as FRAME messages.

Can be used both as a test fixture and as a standalone script for development.
Per ACCEPTANCE_TESTS §J4.
"""

import json
import logging
import socket
import struct
import threading
import time
from pathlib import Path

from evf.camera.protocol import (
    MSG_CONTROL_INFO,
    MSG_FRAME,
    MSG_GET_CONTROLS,
    MSG_HELLO,
    MSG_SET_CONTROL,
    DisconnectError,
    encode_json_message,
    encode_message,
    read_message,
)

logger = logging.getLogger(__name__)

_SAMPLES_DIR = Path(__file__).parent / "samples"

_DEFAULT_HELLO = {
    "protocol_version": 1,
    "backend": "mock-python",
    "backend_version": "0.1.0",
    "camera_model": "MOCK_CAMERA",
    "stream_format": "MJPEG",
    "default_width": 1280,
    "default_height": 720,
    "default_fps": 30,
}

_DEFAULT_CONTROLS = {
    "controls": [
        {
            "id": "exposure",
            "label": "Exposure",
            "type": "int",
            "min": 1,
            "max": 5000,
            "step": 1,
            "cur": 100,
            "unit": "ms",
        },
        {
            "id": "gain",
            "label": "Gain",
            "type": "int",
            "min": 0,
            "max": 255,
            "step": 1,
            "cur": 10,
            "unit": "raw",
        },
    ]
}


class MockCameraServer:
    """A mock camera server that streams sample images over the camera protocol.

    Args:
        host: Bind address.
        port: Bind port (0 for OS-assigned).
        fps: Frame rate for streaming.
        hello: Override HELLO payload dict.
        sample_dir: Directory containing sample PNG/JPEG files.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8764,
        fps: float = 10.0,
        hello: dict | None = None,
        sample_dir: Path | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._fps = fps
        self._hello = hello or dict(_DEFAULT_HELLO)
        self._controls = _deep_copy(_DEFAULT_CONTROLS)
        self._sample_dir = sample_dir or _SAMPLES_DIR
        self._server_sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frames: list[bytes] = []
        self._set_control_log: list[dict] = []

    def start(self) -> None:
        self._load_frames()
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen(1)
        self._server_sock.settimeout(1.0)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="mock-camera", daemon=True)
        self._thread.start()
        logger.info("Mock camera server listening on %s:%d", self._host, self.port)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        logger.info("Mock camera server stopped")

    @property
    def port(self) -> int:
        if self._server_sock is not None:
            return self._server_sock.getsockname()[1]
        return self._port

    @property
    def set_control_log(self) -> list[dict]:
        return list(self._set_control_log)

    # -- internal -------------------------------------------------------------

    def _load_frames(self) -> None:
        """Load sample images as JPEG bytes."""
        self._frames = []
        for name in sorted(self._sample_dir.glob("*.png")):
            self._frames.append(name.read_bytes())
        if not self._frames:
            # Fallback: generate a tiny valid JPEG-like blob
            self._frames = [b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"]
        logger.debug("Loaded %d sample frames", len(self._frames))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                client, addr = self._server_sock.accept()
                logger.info("Mock camera: client connected from %s:%d", *addr)
                self._handle_client(client)
            except socket.timeout:
                continue
            except OSError:
                if not self._stop_event.is_set():
                    logger.error("Mock camera server socket error")
                break

    def _handle_client(self, client: socket.socket) -> None:
        try:
            client.settimeout(1.0)

            # Send HELLO
            client.sendall(encode_json_message(MSG_HELLO, self._hello))

            # Wait for client HELLO
            msg_type, payload = read_message(client)
            if msg_type != MSG_HELLO:
                logger.warning("Expected HELLO from client, got 0x%02x", msg_type)
                client.close()
                return
            logger.debug("Client HELLO: %s", payload.decode("utf-8", errors="replace"))

            # Send CONTROL_INFO
            client.sendall(encode_json_message(MSG_CONTROL_INFO, self._controls))

            # Start streaming + handle incoming commands
            self._stream_loop(client)
        except (DisconnectError, ConnectionResetError, BrokenPipeError, OSError) as exc:
            logger.info("Mock camera: client disconnected (%s)", exc)
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _stream_loop(self, client: socket.socket) -> None:
        frame_idx = 0
        interval = 1.0 / self._fps

        while not self._stop_event.is_set():
            # Send a frame
            frame_data = self._frames[frame_idx % len(self._frames)]
            try:
                client.sendall(encode_message(MSG_FRAME, frame_data))
            except (BrokenPipeError, ConnectionResetError, OSError):
                raise DisconnectError("Send failed")
            frame_idx += 1

            # Check for incoming commands (non-blocking)
            self._poll_commands(client)

            time.sleep(interval)

    def _poll_commands(self, client: socket.socket) -> None:
        """Non-blocking check for incoming app→camera messages."""
        import select

        readable, _, _ = select.select([client], [], [], 0)
        if not readable:
            return

        try:
            msg_type, payload = read_message(client)
        except (DisconnectError, socket.timeout):
            return

        if msg_type == MSG_SET_CONTROL:
            try:
                cmd = json.loads(payload.decode("utf-8"))
                self._apply_set_control(cmd)
                self._set_control_log.append(cmd)
                client.sendall(encode_json_message(MSG_CONTROL_INFO, self._controls))
                logger.info("Mock camera: SET_CONTROL %s", cmd)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.error("Bad SET_CONTROL payload: %s", exc)
        elif msg_type == MSG_GET_CONTROLS:
            client.sendall(encode_json_message(MSG_CONTROL_INFO, self._controls))
            logger.debug("Mock camera: sent CONTROL_INFO (GET_CONTROLS)")
        else:
            logger.debug("Mock camera: ignoring message type 0x%02x", msg_type)

    def _apply_set_control(self, cmd: dict) -> None:
        control_id = cmd.get("id")
        value = cmd.get("value")
        for ctrl in self._controls["controls"]:
            if ctrl["id"] == control_id:
                clamped = max(ctrl["min"], min(ctrl["max"], value))
                ctrl["cur"] = clamped
                break


def _deep_copy(d):
    import copy
    return copy.deepcopy(d)


# -- standalone entry point --------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    server = MockCameraServer(port=8764, fps=10)
    server.start()
    print(f"Mock camera server running on localhost:{server.port}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("Stopped.")
