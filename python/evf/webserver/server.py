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

"""Mobile web interface — aiohttp HTTP + WebSocket server.

Serves data/web/index.html and pushes JSON state at ~10 Hz over WebSocket.
Runs in a dedicated daemon thread with its own asyncio event loop.
"""

import asyncio
import json
import logging
import math
import socket
import threading
import time
from typing import Callable

from aiohttp import web

from evf.config.manager import ConfigManager
from evf.engine.goto_target import GotoTarget
from evf.engine.navigation import compute_navigation, edge_arrow_position
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.paths import sounds_dir, web_dir

logger = logging.getLogger(__name__)

# Must match window.py constants exactly
_FOV_H = 8.86   # horizontal FOV in degrees
_IMG_W = 1280
_IMG_H = 720


def _local_ip() -> str:
    """Best-effort LAN IP address (doesn't send any data)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def _compute_origin(config: ConfigManager) -> tuple[float, float]:
    """Pixel position of the sync offset (pointing center) in image coords.

    Mirrors window.py._sync_offset_pixel() exactly.
    Falls back to image center when no sync calibration is available.
    """
    cx, cy = _IMG_W / 2.0, _IMG_H / 2.0
    d_body = config.sync_d_body
    if d_body is not None and d_body[2] > 0.1:
        scale = _IMG_W / (2.0 * math.tan(math.radians(_FOV_H / 2.0)))
        cx += (-d_body[0] / d_body[2]) * scale
        cy += (-d_body[1] / d_body[2]) * scale
    return cx, cy


class WebServer:
    """HTTP + WebSocket server for the mobile web interface.

    Always-on subsystem: started with the engine, stopped on shutdown.
    HTTP GET /          — serves data/web/index.html
    HTTP GET /sounds/*  — serves WAV audio files
    WebSocket /ws       — pushes JSON state at ~10 Hz to all clients
    """

    def __init__(
        self,
        pointing: PointingState,
        state_machine: StateMachine,
        goto_target: GotoTarget,
        config: ConfigManager,
        *,
        solver_failures: Callable[[], int] | None = None,
        stellarium_object: Callable[[], dict | None] | None = None,
    ) -> None:
        self._pointing = pointing
        self._state_machine = state_machine
        self._goto_target = goto_target
        self._config = config
        self._solver_failures = solver_failures
        self._stellarium_object = stellarium_object

        self._clients: set[web.WebSocketResponse] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._url: str | None = None

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="webserver", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        logger.info("Web server stopped")

    @property
    def url(self) -> str | None:
        """LAN URL of the mobile interface, available after start()."""
        return self._url

    # -- internal -------------------------------------------------------------

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as exc:
            logger.error("Web server error: %s", exc)

    async def _serve(self) -> None:
        port = self._config.web_port
        ip = _local_ip()
        self._url = f"http://{ip}:{port}"
        logger.info("Mobile web interface at %s", self._url)

        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/ws", self._handle_ws)
        app.router.add_static("/sounds", sounds_dir(), name="sounds")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info("Web server listening on port %d", port)

        await self._broadcast_loop()

    async def _handle_index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(web_dir() / "index.html")

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        logger.info("Web client connected: %s", request.remote)
        try:
            async for _msg in ws:
                pass  # read-only; ignore any incoming messages
        finally:
            self._clients.discard(ws)
            logger.info("Web client disconnected: %s", request.remote)
        return ws

    async def _broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(0.1)  # 10 Hz
            if not self._clients:
                continue
            try:
                payload = json.dumps(self._build_payload())
            except Exception as exc:
                logger.debug("Payload build error: %s", exc)
                continue
            dead: set[web.WebSocketResponse] = set()
            for ws in list(self._clients):
                try:
                    await ws.send_str(payload)
                except Exception:
                    dead.add(ws)
            self._clients -= dead

    # -- payload --------------------------------------------------------------

    def _build_payload(self) -> dict:
        state = self._state_machine.state
        snap = self._pointing.read()
        target = self._goto_target.read()
        failures = self._solver_failures() if self._solver_failures else 0
        origin_x, origin_y = _compute_origin(self._config)
        dx_off = origin_x - _IMG_W / 2.0
        dy_off = origin_y - _IMG_H / 2.0

        pointing_data = {
            "valid": snap.valid,
            "ra_deg": snap.ra_j2000,
            "dec_deg": snap.dec_j2000,
            "roll_deg": snap.roll,
            "matches": snap.matches,
            "prob": snap.prob,
            "solve_age_s": (
                round(time.monotonic() - snap.last_success_timestamp, 1)
                if snap.valid else None
            ),
        }

        nav_data = self._build_nav(snap, target, origin_x, origin_y, dx_off, dy_off)

        return {
            "state": state.value,
            "failures": failures,
            "pointing": pointing_data,
            "nav": nav_data,
            "origin_x": origin_x,
            "origin_y": origin_y,
            "image_w": _IMG_W,
            "image_h": _IMG_H,
            "finder_rotation": self._config.finder_rotation,
            "fov_h_deg": _FOV_H,
        }

    def _build_nav(self, snap, target, origin_x, origin_y, dx_off, dy_off) -> dict | None:
        if not target.active:
            return None

        obj_name = None
        if self._stellarium_object:
            obj = self._stellarium_object()
            if obj:
                obj_name = obj.get("localized-name") or obj.get("name")

        base = {
            "active": True,
            "target_name": obj_name,
            "target_ra_deg": target.ra_j2000,
            "target_dec_deg": target.dec_j2000,
        }

        if not snap.valid:
            return {**base, "separation_deg": None, "direction_text": "--",
                    "in_fov": False, "pixel_x": None, "pixel_y": None,
                    "camera_angle_deg": None, "edge_x": None, "edge_y": None,
                    "edge_angle_deg": None}

        nav = compute_navigation(
            snap.ra_j2000, snap.dec_j2000, snap.roll,
            target.ra_j2000, target.dec_j2000,
            _FOV_H, _IMG_W, _IMG_H,
        )

        edge_x = edge_y = edge_angle = None
        if not nav.in_fov:
            if nav.pixel_x is not None:
                edge_x, edge_y, edge_angle = edge_arrow_position(
                    nav.pixel_x + dx_off, nav.pixel_y + dy_off,
                    _IMG_W, _IMG_H, margin=68,
                    origin_x=origin_x, origin_y=origin_y,
                )
            else:
                # Target behind camera — derive direction from camera_angle_deg
                far = max(_IMG_W, _IMG_H) * 10.0
                rad = math.radians(nav.camera_angle_deg)
                far_x = origin_x + far * math.sin(rad)
                far_y = origin_y - far * math.cos(rad)
                edge_x, edge_y, edge_angle = edge_arrow_position(
                    far_x, far_y, _IMG_W, _IMG_H, margin=68,
                    origin_x=origin_x, origin_y=origin_y,
                )

        return {
            **base,
            "separation_deg": nav.separation_deg,
            "direction_text": nav.direction_text,
            "in_fov": nav.in_fov,
            "pixel_x": nav.pixel_x,
            "pixel_y": nav.pixel_y,
            "camera_angle_deg": nav.camera_angle_deg,
            "edge_x": edge_x,
            "edge_y": edge_y,
            "edge_angle_deg": edge_angle,
        }
