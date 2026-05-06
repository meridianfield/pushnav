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

"""Tests for POST /api/* action endpoints."""

import threading
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientSession

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver.server import WebServer


@pytest.fixture
def server_and_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    cfg._data["webserver"]["port"] = 0  # ephemeral; bypasses validator
    actions = MagicMock()
    ws = WebServer(
        PointingState(), StateMachine(), GotoTarget(), cfg,
        frame_buffer=LatestFrame(),
        actions=actions,
    )
    ws.start()
    for _ in range(20):
        if ws._port is not None:
            break
        threading.Event().wait(0.05)
    yield ws, actions
    ws.stop()


@pytest.mark.asyncio
async def test_wizard_advance(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/wizard/advance") as resp:
            assert resp.status == 204
    actions.step_advance.assert_called_once()


@pytest.mark.asyncio
async def test_sync_select_with_idx(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/sync/select", json={"idx": 2}) as resp:
            assert resp.status == 204
    actions.set_sync_selected.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_set_control(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/control",
                          json={"name": "exposure", "value": 42}) as resp:
            assert resp.status == 204
    actions.set_control.assert_called_once_with("exposure", 42)


@pytest.mark.asyncio
async def test_settings_audio(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/settings",
                          json={"audio_enabled": False}) as resp:
            assert resp.status == 204
    actions.set_audio_enabled.assert_called_once_with(False)
