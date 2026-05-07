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
import threading
import time
from typing import Callable, Protocol

from aiohttp import web

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.navigation import compute_navigation, edge_arrow_position
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.network import local_ip
from evf.paths import sounds_dir, web_dir

logger = logging.getLogger(__name__)

_MAX_WS_CLIENTS = 10  # cap concurrent WebSocket connections
_MAX_MJPEG_CLIENTS = 4
_MJPEG_BOUNDARY = b"frame"
_MJPEG_INTERVAL = 0.1  # 10 Hz

# Must match window.py constants exactly
_FOV_H = 8.86   # horizontal FOV in degrees
_IMG_W = 1280
_IMG_H = 720


class EngineActions(Protocol):
    """Action surface the WebServer calls into. Implemented by Engine."""

    def step_advance(self) -> None: ...
    def sync_retry(self) -> None: ...
    def set_sync_selected(self, idx: int) -> None: ...
    def use_previous_calibration(self) -> None: ...
    def set_control(self, name: str, value: int) -> None: ...
    def clear_goto_target(self) -> None: ...
    def set_audio_enabled(self, enabled: bool) -> None: ...
    def set_hidpi(self, enabled: bool) -> None: ...


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


@web.middleware
async def _security_headers_middleware(request: web.Request, handler) -> web.StreamResponse:
    """Add basic security headers to every HTTP response."""
    response = await handler(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:",
    )
    return response


def _is_local_origin(origin: str) -> bool:
    """Return True if the WebSocket Origin header looks like a local address."""
    import urllib.parse
    try:
        host = urllib.parse.urlparse(origin).hostname or ""
        return (
            host == "localhost"
            or host.startswith("127.")
            or host.startswith("192.168.")
            or host.startswith("10.")
            or host.startswith("172.")
        )
    except Exception:
        return False


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
        frame_buffer: LatestFrame | None = None,
        solver_failures: Callable[[], int] | None = None,
        stellarium_object: Callable[[], dict | None] | None = None,
        camera_controls: Callable[[], list[dict] | None] | None = None,
        sync_state: Callable[[], dict] | None = None,
        activity: Callable[[], dict] | None = None,
        actions: "EngineActions | None" = None,
    ) -> None:
        self._pointing = pointing
        self._state_machine = state_machine
        self._goto_target = goto_target
        self._config = config
        self._frame_buffer = frame_buffer
        self._solver_failures = solver_failures
        self._stellarium_object = stellarium_object
        self._camera_controls = camera_controls
        self._sync_state = sync_state
        self._activity = activity
        self._actions = actions

        self._clients: set[web.WebSocketResponse] = set()
        self._mjpeg_clients: int = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._url: str | None = None
        self._port: int | None = None  # actual bound port (for tests on ephemeral port)

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
        ip = local_ip()
        if ip is None:
            self._url = None
            logger.warning(
                "Mobile web interface listening on port %d but no LAN IP "
                "detected — mobile devices cannot reach the server",
                port,
            )
        else:
            self._url = f"http://{ip}:{port}"
            logger.info("Mobile web interface at %s", self._url)

        app = web.Application(middlewares=[_security_headers_middleware])
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/ws", self._handle_ws)
        app.router.add_get("/frame.mjpg", self._handle_mjpeg)
        app.router.add_post("/api/wizard/advance", self._api_wizard_advance)
        app.router.add_post("/api/sync/retry", self._api_sync_retry)
        app.router.add_post("/api/sync/select", self._api_sync_select)
        app.router.add_post("/api/calibration/use-previous", self._api_use_previous_calibration)
        app.router.add_post("/api/control", self._api_set_control)
        app.router.add_post("/api/goto/clear", self._api_goto_clear)
        app.router.add_post("/api/settings", self._api_settings)
        app.router.add_static("/sounds", sounds_dir(), name="sounds")
        from evf.paths import web_dist_dir
        dist = web_dist_dir()
        if dist.exists():
            app.router.add_static("/static", dist, name="react_static")
        app.router.add_static("/assets", web_dir(), name="assets")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        # Capture the actually-bound port only when caller asked for ephemeral.
        # Reaches into aiohttp internals, so we restrict to the test path.
        if port == 0:
            try:
                self._port = site._server.sockets[0].getsockname()[1]
            except Exception:
                self._port = port
        else:
            self._port = port
        logger.info("Web server listening on port %d", self._port)

        await self._broadcast_loop()

    async def _handle_index(self, request: web.Request) -> web.FileResponse:
        """Serve the React app shell. Falls back to legacy data/web/index.html if dist missing."""
        from evf.paths import web_dist_dir
        dist = web_dist_dir()
        if (dist / "index.html").exists():
            return web.FileResponse(dist / "index.html")
        return web.FileResponse(web_dir() / "index.html")

    # -- MJPEG frame stream ---------------------------------------------------

    async def _handle_mjpeg(self, request: web.Request) -> web.StreamResponse:
        """Multipart MJPEG stream of the latest camera frame.

        Browsers and OS webviews render multipart/x-mixed-replace natively in
        an <img> tag, so the React UI does not need any JS-side JPEG decoding.
        """
        if self._frame_buffer is None:
            return web.Response(status=503, text="No frame buffer")
        if self._mjpeg_clients >= _MAX_MJPEG_CLIENTS:
            logger.warning("MJPEG client limit reached (%d), rejecting", _MAX_MJPEG_CLIENTS)
            raise web.HTTPServiceUnavailable(reason="Too many MJPEG clients")
        self._mjpeg_clients += 1
        try:
            resp = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": (
                        "multipart/x-mixed-replace; "
                        f"boundary={_MJPEG_BOUNDARY.decode()}"
                    ),
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                },
            )
            await resp.prepare(request)
            last_frame_id = -1
            try:
                while True:
                    jpeg, _ts, fid = self._frame_buffer.get()
                    if jpeg is not None and fid != last_frame_id:
                        last_frame_id = fid
                        part = (
                            b"--" + _MJPEG_BOUNDARY + b"\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                            + jpeg + b"\r\n"
                        )
                        await resp.write(part)
                    await asyncio.sleep(_MJPEG_INTERVAL)
            except (asyncio.CancelledError, ConnectionResetError):
                pass
        finally:
            self._mjpeg_clients -= 1
        return resp

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        # Reject if connection cap reached
        if len(self._clients) >= _MAX_WS_CLIENTS:
            logger.warning("WebSocket connection limit reached (%d), rejecting", _MAX_WS_CLIENTS)
            raise web.HTTPServiceUnavailable(reason="Too many clients")

        # Warn on non-local origin (informational — LAN clients have no Origin header)
        origin = request.headers.get("Origin", "")
        if origin and not _is_local_origin(origin):
            logger.warning("WebSocket connection from non-local origin: %s", origin)

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        logger.info("Web client connected")
        try:
            async for _msg in ws:
                pass  # read-only; ignore any incoming messages
        finally:
            self._clients.discard(ws)
            logger.info("Web client disconnected")
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

    # -- API actions ----------------------------------------------------------

    async def _handle_api(self, request: web.Request, fn) -> web.Response:
        """Run a synchronous engine action and return 204."""
        if self._actions is None:
            return web.Response(status=503, text="No actions wired")
        try:
            await asyncio.to_thread(fn)
        except Exception as exc:
            logger.exception("API action failed: %s", exc)
            return web.Response(status=500, text=str(exc))
        return web.Response(status=204)

    async def _api_wizard_advance(self, request):
        return await self._handle_api(request, lambda: self._actions.step_advance())

    async def _api_sync_retry(self, request):
        return await self._handle_api(request, lambda: self._actions.sync_retry())

    async def _api_sync_select(self, request):
        body = await request.json()
        idx = int(body["idx"])
        return await self._handle_api(request, lambda: self._actions.set_sync_selected(idx))

    async def _api_use_previous_calibration(self, request):
        return await self._handle_api(request, lambda: self._actions.use_previous_calibration())

    async def _api_set_control(self, request):
        body = await request.json()
        name = str(body["name"])
        value = int(body["value"])
        return await self._handle_api(request, lambda: self._actions.set_control(name, value))

    async def _api_goto_clear(self, request):
        return await self._handle_api(request, lambda: self._actions.clear_goto_target())

    async def _api_settings(self, request):
        body = await request.json()
        if "audio_enabled" in body:
            resp = await self._handle_api(
                request,
                lambda: self._actions.set_audio_enabled(bool(body["audio_enabled"])),
            )
            if resp.status >= 400:
                return resp
        if "hidpi" in body:
            return await self._handle_api(
                request,
                lambda: self._actions.set_hidpi(bool(body["hidpi"])),
            )
        return web.Response(status=204)

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

        controls = self._camera_controls() if self._camera_controls else []
        sync_blk = self._sync_state() if self._sync_state else {
            "in_progress": False, "candidates": [], "selected_idx": None, "error": None,
        }
        activity_blk = self._activity() if self._activity else {}
        camera_blk = {
            "connected": True if (self._frame_buffer and self._frame_buffer.get()[0]) else False,
            "all_centroids": snap.all_centroids if snap.valid else None,
            "matched_centroids": snap.matched_centroids if snap.valid else None,
        }

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
            "has_calibration": self._config.has_calibration,
            "image_size": list(snap.image_size) if snap.valid and snap.image_size else None,
            "controls": controls or [],
            "sync": sync_blk,
            "stellarium": activity_blk.get("stellarium", {"active": False, "address": None}),
            "lx200":      activity_blk.get("lx200",      {"active": False, "address": None}),
            "webserver":  activity_blk.get("webserver",  {"url": None}),
            "audio_enabled": activity_blk.get("audio_enabled", True),
            "camera": camera_blk,
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
