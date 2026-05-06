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

"""Tests for the MJPEG frame stream endpoint."""

import threading
import time

import pytest
from aiohttp import ClientSession

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver.server import WebServer

# Smallest valid-looking JPEG: SOI + APP0 + DQT + SOF0 + DHT + SOS + EOI is
# overkill for this test — we only assert the multipart stream contains a
# JPEG SOI (0xFFD8), so a short blob starting with the SOI marker is enough.
_TINY_JPEG = b"\xff\xd8\xff\xd9"


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Start a WebServer on an ephemeral port for testing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    # web_port=0 asks the OS to assign an ephemeral port. The setter
    # validates the range, so write directly to the underlying dict.
    cfg._data["webserver"]["port"] = 0
    fb = LatestFrame()
    fb.set(_TINY_JPEG, time.time(), 1)
    ws = WebServer(PointingState(), StateMachine(), GotoTarget(), cfg, frame_buffer=fb)
    ws.start()
    # Wait briefly for the server thread to bind and capture the port.
    for _ in range(40):
        if ws._port is not None:
            break
        threading.Event().wait(0.05)
    assert ws._port is not None, "Web server did not bind in time"
    yield ws
    ws.stop()


@pytest.mark.asyncio
async def test_mjpeg_returns_multipart_with_jpeg_part(server):
    async with ClientSession() as s:
        async with s.get(f"http://127.0.0.1:{server._port}/frame.mjpg") as resp:
            assert resp.status == 200
            assert "multipart/x-mixed-replace" in resp.headers["Content-Type"]
            # Read first part: should contain a JPEG SOI marker (0xFFD8).
            chunk = await resp.content.read(4096)
            assert b"\xff\xd8" in chunk
