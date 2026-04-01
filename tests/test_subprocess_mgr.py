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

"""Tests for SubprocessManager (Phase 5).

Uses MockCameraServer in-process on OS-assigned ports to avoid needing
the real Swift camera_server binary.
"""

import time

import pytest

from evf.camera.subprocess_mgr import SubprocessManager
from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.state import EngineState, StateMachine
from tests.mock_camera_server import MockCameraServer


class _NoopSubprocessManager(SubprocessManager):
    """SubprocessManager that skips Popen — for use with MockCameraServer."""

    _BACKOFF = [0.1, 0.2, 0.3, 0.4, 0.5]
    _MONITOR_INTERVAL = 0.1
    _PORT_TIMEOUT = 1.0
    _PORT_POLL_INTERVAL = 0.05
    _FRAME_STALL_TIMEOUT = 0.5

    def _spawn_process(self):
        pass  # Mock server is already running externally

    def _terminate_process(self):
        pass  # No real process to kill


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def frame_buffer():
    return LatestFrame()


@pytest.fixture()
def state_machine():
    return StateMachine()


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)


@pytest.fixture()
def mock_server():
    """Start a MockCameraServer on an OS-assigned port; stop on teardown."""
    server = MockCameraServer(port=0, fps=20)
    server.start()
    yield server
    server.stop()


def _make_mgr(frame_buffer, state_machine, config, port):
    return _NoopSubprocessManager(
        frame_buffer,
        state_machine,
        config,
        binary_path="/dev/null",
        port=port,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSubprocessManager:
    def test_start_and_connect(self, frame_buffer, state_machine, config, mock_server):
        """Mock server on random port, SubprocessManager connects, HELLO succeeds."""
        mgr = _make_mgr(frame_buffer, state_machine, config, mock_server.port)
        hello = mgr.start()

        assert hello["protocol_version"] == 1
        assert hello["stream_format"] == "MJPEG"
        assert mgr.running
        assert mgr.client is not None
        assert len(mgr.client.controls) == 2
        ids = {c["id"] for c in mgr.client.controls}
        assert "exposure" in ids
        assert "gain" in ids

        mgr.stop()

    def test_stop_cleans_up(self, frame_buffer, state_machine, config, mock_server):
        """After stop(), client is None and running is False."""
        mgr = _make_mgr(frame_buffer, state_machine, config, mock_server.port)
        mgr.start()
        time.sleep(0.2)
        assert mgr.running

        mgr.stop()
        assert mgr.client is None
        assert not mgr.running

    def test_port_wait_timeout(self, frame_buffer, state_machine, config):
        """No server listening — start() raises RuntimeError within timeout."""
        # Bind and immediately close to get a port that nothing listens on
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        mgr = _make_mgr(frame_buffer, state_machine, config, port)
        mgr._PORT_TIMEOUT = 0.5  # speed up for this test

        with pytest.raises(RuntimeError, match="not listening"):
            mgr.start()

    def test_crash_recovery(self, frame_buffer, state_machine, config):
        """Stop mock server mid-stream -> RECONNECTING -> restart mock -> SETUP."""
        server = MockCameraServer(port=0, fps=20)
        server.start()
        port = server.port

        config.exposure = 200
        config.gain = 50

        mgr = _make_mgr(frame_buffer, state_machine, config, port)
        mgr.start()
        time.sleep(0.3)
        assert mgr.running

        # Kill the mock server — client will detect disconnect
        server.stop()
        # Wait for disconnect detection + transition to RECONNECTING
        deadline = time.monotonic() + 5.0
        while state_machine.state != EngineState.RECONNECTING and time.monotonic() < deadline:
            time.sleep(0.05)
        assert state_machine.state == EngineState.RECONNECTING

        # Restart mock server on the same port so recovery can reconnect
        server2 = MockCameraServer(port=port, fps=20)
        server2.start()

        # Wait for recovery to succeed (transition to SETUP)
        deadline = time.monotonic() + 10.0
        while state_machine.state != EngineState.SETUP and time.monotonic() < deadline:
            time.sleep(0.1)

        assert state_machine.state == EngineState.SETUP
        assert mgr.running

        # Verify config was restored via SET_CONTROL
        time.sleep(0.3)  # let SET_CONTROL messages arrive
        set_ids = {c["id"] for c in server2.set_control_log}
        assert "exposure" in set_ids
        assert "gain" in set_ids

        mgr.stop()
        server2.stop()

    def test_frame_stall_triggers_recovery(self, frame_buffer, state_machine, config):
        """No frames for FRAME_STALL_TIMEOUT -> RECONNECTING -> recovery."""
        server = MockCameraServer(port=0, fps=20)
        server.start()
        port = server.port

        mgr = _make_mgr(frame_buffer, state_machine, config, port)
        mgr.start()
        time.sleep(0.3)
        assert mgr.running

        # Simulate frame stall by backdating last_frame_time
        mgr.client._last_frame_time = time.monotonic() - 10.0
        # Also stop the real server so no new frames reset the timer
        server.stop()

        # Wait for stall detection -> RECONNECTING
        deadline = time.monotonic() + 5.0
        while state_machine.state != EngineState.RECONNECTING and time.monotonic() < deadline:
            time.sleep(0.05)
        assert state_machine.state == EngineState.RECONNECTING

        # Restart mock so recovery succeeds
        server2 = MockCameraServer(port=port, fps=20)
        server2.start()

        deadline = time.monotonic() + 10.0
        while state_machine.state != EngineState.SETUP and time.monotonic() < deadline:
            time.sleep(0.1)
        assert state_machine.state == EngineState.SETUP

        mgr.stop()
        server2.stop()

    def test_retry_exhaustion(self, frame_buffer, state_machine, config):
        """Server stays down -> 5 retries with backoff -> ERROR state."""
        server = MockCameraServer(port=0, fps=20)
        server.start()
        port = server.port

        mgr = _make_mgr(frame_buffer, state_machine, config, port)
        mgr.start()
        time.sleep(0.3)
        assert mgr.running

        # Kill and don't restart
        server.stop()

        # Wait for all retries to exhaust → ERROR
        # Total: sum(backoff) + 5 * port_timeout = 1.5 + 5*1.0 = 6.5s max
        deadline = time.monotonic() + 15.0
        while state_machine.state != EngineState.ERROR and time.monotonic() < deadline:
            time.sleep(0.1)

        assert state_machine.state == EngineState.ERROR
        mgr.stop()

    def test_normal_shutdown(self, frame_buffer, state_machine, config, mock_server):
        """stop() terminates cleanly without entering recovery."""
        mgr = _make_mgr(frame_buffer, state_machine, config, mock_server.port)
        mgr.start()
        time.sleep(0.3)
        assert mgr.running
        assert state_machine.state == EngineState.SETUP

        mgr.stop()
        assert not mgr.running
        assert mgr.client is None
        # State should still be SETUP — no crash recovery triggered
        assert state_machine.state == EngineState.SETUP
