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

"""Tests for camera protocol codec and client (ACCEPTANCE_TESTS §J4)."""

import json
import struct
import time

import pytest

from evf.camera.protocol import (
    MSG_CONTROL_INFO,
    MSG_ERROR,
    MSG_FRAME,
    MSG_GET_CONTROLS,
    MSG_HELLO,
    MSG_SET_CONTROL,
    DisconnectError,
    _HEADER_FMT,
    _HEADER_SIZE,
    encode_json_message,
    encode_message,
    read_message,
    type_name,
)
from evf.camera.client import CameraClient, ProtocolError
from evf.engine.frame_buffer import LatestFrame
from tests.mock_camera_server import MockCameraServer


# ---------------------------------------------------------------------------
# Protocol codec
# ---------------------------------------------------------------------------

class TestProtocolCodec:
    def test_encode_empty_payload(self):
        msg = encode_message(MSG_GET_CONTROLS)
        assert len(msg) == _HEADER_SIZE
        msg_type, length = struct.unpack(_HEADER_FMT, msg)
        assert msg_type == MSG_GET_CONTROLS
        assert length == 0

    def test_encode_with_payload(self):
        payload = b"hello world"
        msg = encode_message(MSG_FRAME, payload)
        msg_type, length = struct.unpack(_HEADER_FMT, msg[:_HEADER_SIZE])
        assert msg_type == MSG_FRAME
        assert length == len(payload)
        assert msg[_HEADER_SIZE:] == payload

    def test_encode_json_message(self):
        obj = {"id": "exposure", "value": 250}
        msg = encode_json_message(MSG_SET_CONTROL, obj)
        msg_type, length = struct.unpack(_HEADER_FMT, msg[:_HEADER_SIZE])
        assert msg_type == MSG_SET_CONTROL
        decoded = json.loads(msg[_HEADER_SIZE:].decode("utf-8"))
        assert decoded == obj

    def test_type_name_known(self):
        assert type_name(MSG_HELLO) == "HELLO"
        assert type_name(MSG_FRAME) == "FRAME"

    def test_type_name_unknown(self):
        assert "UNKNOWN" in type_name(0xFF)


# ---------------------------------------------------------------------------
# CameraClient + MockCameraServer integration
# ---------------------------------------------------------------------------

class TestCameraClientIntegration:
    def _start_server(self, **kwargs):
        server = MockCameraServer(port=0, **kwargs)
        server.start()
        return server

    def test_handshake(self):
        """Connect, perform HELLO handshake, receive CONTROL_INFO."""
        server = self._start_server()
        try:
            buf = LatestFrame()
            client = CameraClient(buf, port=server.port)
            hello = client.connect(timeout=5.0)

            assert hello["protocol_version"] == 1
            assert hello["stream_format"] == "MJPEG"

            controls = client.controls
            assert len(controls) == 2
            ids = {c["id"] for c in controls}
            assert "exposure" in ids
            assert "gain" in ids

            client.stop()
        finally:
            server.stop()

    def test_receive_frames(self):
        """Start receiving and verify frames arrive in the buffer."""
        server = self._start_server(fps=20)
        try:
            buf = LatestFrame()
            client = CameraClient(buf, port=server.port)
            client.connect(timeout=5.0)
            client.start_receiving()

            # Wait for some frames
            time.sleep(0.5)
            data, ts, fid = buf.get()
            assert data is not None
            assert fid > 0
            assert ts > 0

            client.stop()
        finally:
            server.stop()

    def test_frame_overwrite(self):
        """Verify only the latest frame is kept (no queue)."""
        server = self._start_server(fps=20)
        try:
            buf = LatestFrame()
            client = CameraClient(buf, port=server.port)
            client.connect(timeout=5.0)
            client.start_receiving()

            time.sleep(0.5)
            _, _, fid1 = buf.get()
            time.sleep(0.3)
            _, _, fid2 = buf.get()
            assert fid2 > fid1, "Frame ID should increase (latest frame only)"

            client.stop()
        finally:
            server.stop()

    def test_set_control(self):
        """Send SET_CONTROL, verify mock server logs it and sends updated CONTROL_INFO."""
        server = self._start_server(fps=10)
        try:
            buf = LatestFrame()
            client = CameraClient(buf, port=server.port)
            client.connect(timeout=5.0)
            client.start_receiving()

            # Wait for frames to flow
            time.sleep(0.3)

            client.set_control("exposure", 500)
            time.sleep(0.5)

            # Check that the server logged the command
            assert len(server.set_control_log) >= 1
            assert server.set_control_log[-1]["id"] == "exposure"
            assert server.set_control_log[-1]["value"] == 500

            client.stop()
        finally:
            server.stop()

    def test_get_controls(self):
        """Send GET_CONTROLS, verify we receive updated CONTROL_INFO."""
        server = self._start_server(fps=10)
        try:
            buf = LatestFrame()
            received_updates = []
            client = CameraClient(buf, port=server.port)
            client.on_controls_update(lambda c: received_updates.append(c))
            client.connect(timeout=5.0)
            client.start_receiving()

            time.sleep(0.3)
            client.get_controls()
            time.sleep(0.5)

            # Should have received at least one CONTROL_INFO update from GET_CONTROLS
            assert len(received_updates) >= 1

            client.stop()
        finally:
            server.stop()

    def test_disconnect_detection(self):
        """Stop the server mid-stream; client detects disconnect."""
        server = self._start_server(fps=10)
        try:
            buf = LatestFrame()
            client = CameraClient(buf, port=server.port)
            client.connect(timeout=5.0)
            client.start_receiving()

            time.sleep(0.3)
            assert client.connected is True

            # Kill the server
            server.stop()
            time.sleep(2.0)

            assert client.connected is False
        finally:
            client.stop()

    def test_protocol_version_mismatch(self):
        """Server sends wrong protocol version; client raises ProtocolError."""
        bad_hello = {
            "protocol_version": 999,
            "backend": "mock",
            "stream_format": "MJPEG",
        }
        server = self._start_server(hello=bad_hello)
        try:
            buf = LatestFrame()
            client = CameraClient(buf, port=server.port)
            with pytest.raises(ProtocolError, match="version mismatch"):
                client.connect(timeout=5.0)
            client.stop()
        finally:
            server.stop()

    def test_error_callback(self):
        """Verify the error callback is invoked when an ERROR message would be received."""
        # This tests the handler path; in real use the server sends ERROR on failure.
        # We test via the codec directly since the mock server doesn't send errors.
        server = self._start_server(fps=5)
        try:
            buf = LatestFrame()
            errors = []
            client = CameraClient(buf, port=server.port)
            client.on_error(lambda msg: errors.append(msg))
            client.connect(timeout=5.0)

            # Manually invoke the handler to verify wiring
            client._handle_message(MSG_ERROR, b"test error message")
            assert len(errors) == 1
            assert errors[0] == "test error message"

            client.stop()
        finally:
            server.stop()
