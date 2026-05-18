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

"""Engine coordinator — wires all components together.

Per SPEC_ARCHITECTURE.md and impl0.md §Phase 8.
Central coordinator that owns the lifecycle of every subsystem.
"""

import io
import json
import logging
import threading
import time
from pathlib import Path

from evf.camera.subprocess_mgr import SubprocessManager
from evf.config.logging_setup import setup_logging
from evf.config.manager import ConfigManager
from evf.engine.audio import AudioAlert
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.sample_injector import SampleInjector
from evf.engine.state import EngineState, StateMachine
from evf.solver.solver import PlateSolver
import numpy as np

from evf.solver.sync import (
    SyncCandidate,
    auto_select,
    build_sync_candidates,
    compute_body_frame_sync,
)
from evf.network import local_ip
from evf.paths import version_json
from evf.solver.thread import SolverThread
from evf.lx200.server import Lx200Server
from evf.stellarium.server import StellariumServer
from evf.webserver.server import WebServer

logger = logging.getLogger(__name__)

_VERSION_PATH = version_json()


def _read_app_version() -> str:
    """Read app_version string from VERSION.json at engine init.

    Falls back to '0.0.0' if the file is missing or malformed so that the
    LX200 :GVN# reply always returns a well-formed 'PushNav <version>#'.
    """
    try:
        with open(_VERSION_PATH) as f:
            data = json.load(f)
        return str(data.get("app_version", "0.0.0"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "0.0.0"


class Engine:
    """Central coordinator that owns all components and manages their lifecycle.

    Startup creates shared data structures (LatestFrame, PointingState,
    StateMachine, ConfigManager) and launches subsystems (camera subprocess,
    Stellarium server, solver).  The UI reads from these structures and
    calls back into the engine for tracking toggle and camera control changes.
    """

    def __init__(
        self,
        *,
        dev_mode: bool = False,
        config: ConfigManager | None = None,
    ) -> None:
        # Shared data structures
        self._frame_buffer = LatestFrame()
        self._pointing_state = PointingState()
        self._state_machine = StateMachine()
        self._config = config if config is not None else ConfigManager()
        self._goto_target = GotoTarget()
        self._app_version = _read_app_version()
        self._dev_mode = dev_mode

        # Sample injector (continuous JPEG injection for dev/debug)
        self._sample_injector = SampleInjector(self._frame_buffer)

        # Components (created during startup)
        self._solver: PlateSolver | None = None
        self._solver_thread: SolverThread | None = None
        self._audio: AudioAlert | None = None
        self._subprocess_mgr: SubprocessManager | None = None
        self._stellarium: StellariumServer | None = None
        self._lx200: Lx200Server | None = None
        self._webserver: WebServer | None = None

        # Sync state (two-phase calibration)
        self._sync_lock = threading.Lock()
        self._sync_error: str | None = None
        self._sync_candidates: list[SyncCandidate] | None = None
        self._sync_selected_idx: int | None = None
        self._sync_camera_ra: float = 0.0
        self._sync_camera_dec: float = 0.0
        self._sync_camera_roll: float = 0.0

    # -- properties -----------------------------------------------------------

    @property
    def frame_buffer(self) -> LatestFrame:
        return self._frame_buffer

    @property
    def pointing_state(self) -> PointingState:
        return self._pointing_state

    @property
    def state_machine(self) -> StateMachine:
        return self._state_machine

    @property
    def config(self) -> ConfigManager:
        return self._config

    @property
    def app_version(self) -> str:
        return self._app_version

    @property
    def dev_mode(self) -> bool:
        return self._dev_mode

    @property
    def sample_injector(self) -> SampleInjector:
        return self._sample_injector

    @property
    def camera_connected(self) -> bool:
        """True if the camera subprocess is running and connected."""
        return self._subprocess_mgr is not None and self._subprocess_mgr.running

    @property
    def camera_controls(self) -> list[dict] | None:
        """Return the current camera controls, or None if not connected."""
        if self._subprocess_mgr and self._subprocess_mgr.client:
            return self._subprocess_mgr.client.controls
        return None

    @property
    def consecutive_failures(self) -> int:
        if self._solver_thread:
            return self._solver_thread.consecutive_failures
        return 0

    @property
    def audio_enabled(self) -> bool:
        return self._config.audio_enabled

    @audio_enabled.setter
    def audio_enabled(self, value: bool) -> None:
        self._config.audio_enabled = value
        if self._audio:
            self._audio.enabled = value

    @property
    def goto_target(self) -> GotoTarget:
        return self._goto_target

    def clear_goto_target(self) -> None:
        self._goto_target.clear()

    def set_goto_target(self, ra_deg: float, dec_deg: float) -> None:
        """Set the GOTO target. Used by the catalog 'Set as target' flow."""
        self._goto_target.set(float(ra_deg), float(dec_deg))

    def set_audio_enabled(self, enabled: bool) -> None:
        self.audio_enabled = enabled

    @property
    def location(self) -> dict:
        """Resolve the active observer location.

        Priority:
          1. Stellarium status 'location' field, when a Stellarium client is
             actively reporting one (source='stellarium').
          2. ConfigManager.location, when manually set (source='manual').
          3. None — neither available (source=None, lat/lon both None).
        """
        if self._stellarium is not None:
            status = self._stellarium.stellarium_status
            if status:
                loc = status.get("location") if isinstance(status, dict) else None
                if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
                    return {
                        "latitude": float(loc["latitude"]),
                        "longitude": float(loc["longitude"]),
                        "source": "stellarium",
                    }
        manual = self._config.location
        if manual is not None:
            return {
                "latitude": manual[0],
                "longitude": manual[1],
                "source": "manual",
            }
        return {"latitude": None, "longitude": None, "source": None}

    def set_location(self, latitude: float | None, longitude: float | None) -> None:
        """Persist a manual location. Pass (None, None) to clear."""
        if latitude is None or longitude is None:
            self._config.location = None
        else:
            self._config.location = (float(latitude), float(longitude))

    def inject_sample(self, name: str | None) -> None:
        """Start/stop continuous injection of a sample image (dev only).

        name: one of {"a","b","c","d","orion"} or None to stop.
        """
        from evf.paths import samples_dir
        from evf.engine.sample_injector import load_sample_jpeg

        if not self._dev_mode:
            logger.warning("inject_sample called outside dev_mode — ignoring")
            return
        if name is None:
            self._sample_injector.set_jpeg(None, None)
            self._frame_buffer.clear()
            logger.info("Sample injection stopped")
            return
        sd = samples_dir()
        if sd is None:
            logger.error("Samples directory not available in this build")
            return
        try:
            jpeg = load_sample_jpeg(sd, name)
            self._sample_injector.set_jpeg(jpeg, name)
            logger.info("Sample injection started: %s.png", name)
        except Exception as exc:
            logger.error("Failed to load sample %s: %s", name, exc)

    def inject_target(self, ra_deg: float, dec_deg: float) -> None:
        """Set the GOTO target manually (dev only)."""
        if not self._dev_mode:
            logger.warning("inject_target called outside dev_mode — ignoring")
            return
        self._goto_target.set(ra_deg, dec_deg)
        logger.info("Dev: injected GOTO target at RA %.4f° Dec %.4f°", ra_deg, dec_deg)

    def capture_frame(self) -> Path | None:
        """Save the latest frame to ~/Downloads as PNG. Returns the path or None."""
        from datetime import datetime
        from PIL import Image

        jpeg, _ts, _fid = self._frame_buffer.get()
        if jpeg is None:
            return None
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = Path.home() / "Downloads" / f"evf_capture_{timestamp}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        logger.info("Frame captured: %s", dest)
        return dest

    def set_min_matches(self, value: int) -> None:
        self._config.min_matches = int(value)

    def set_max_prob(self, value: float) -> None:
        self._config.max_prob = float(value)

    @property
    def stellarium_status(self) -> dict | None:
        if self._stellarium:
            return self._stellarium.stellarium_status
        return None

    @property
    def stellarium_object(self) -> dict | None:
        if self._stellarium:
            return self._stellarium.stellarium_object
        return None

    @property
    def stellarium_address(self) -> str | None:
        """Address to paste into desktop Stellarium's Telescope Control plugin.

        Stellarium server binds 127.0.0.1, so the address is always localhost
        regardless of LAN IP — remote machines cannot reach the binary protocol.
        """
        if self._stellarium is None:
            return None
        return f"localhost:{self._stellarium.port}"

    @property
    def lx200_address(self) -> str | None:
        """Address to paste into SkySafari / Stellarium Mobile / INDI / ASCOM.

        LX200 server binds 0.0.0.0 so we advertise the LAN IP (same IP the
        mobile web URL uses) so mobile apps on the same network can connect.

        Returns None when the LX200 server isn't running OR no LAN is
        available — the UI distinguishes these via the lx200_running flag.
        """
        if self._lx200 is None:
            return None
        ip = local_ip()
        if ip is None:
            return None
        return f"{ip}:{self._lx200.port}"

    @property
    def lx200_running(self) -> bool:
        """True if the LX200 server bound its socket successfully."""
        return self._lx200 is not None

    @property
    def stellarium_has_client(self) -> bool:
        """True if the Stellarium server currently has any client connected.

        Stellarium holds a persistent TCP connection, so this is a simple
        boolean — the UI lights the Stellarium activity indicator while it
        is True.
        """
        return self._stellarium is not None and self._stellarium.client_count > 0

    # LX200 clients (notably SkySafari in polling mode) open a fresh TCP
    # connection per command, so "has client connected right now" is almost
    # never True. Instead we expose the time since the last connect or
    # received command and hold the indicator lit for _LX200_INDICATOR_HOLD
    # seconds. The user asked for a minimum hold of 100 ms.
    _LX200_INDICATOR_HOLD = 0.1  # seconds

    @property
    def lx200_active(self) -> bool:
        """True if the LX200 server saw a connect or a command within the
        last _LX200_INDICATOR_HOLD seconds."""
        if self._lx200 is None:
            return False
        last = self._lx200.last_activity_monotonic
        if last == 0.0:
            return False
        return (time.monotonic() - last) < self._LX200_INDICATOR_HOLD

    # -- startup (§8.2) -------------------------------------------------------

    def startup_logging(self) -> None:
        """Initialize logging and log version info."""
        setup_logging(verbose=self._config.verbose, console=True)
        logger.info("EVF starting up")
        self._log_version()

    def startup_solver(self) -> None:
        """Load tetra3rs database (~1s)."""
        try:
            self._solver = PlateSolver()
        except Exception as exc:
            logger.error("Failed to load tetra3rs database: %s", exc)

    def startup_stellarium(self) -> None:
        """Start Stellarium TCP server."""
        try:
            self._stellarium = StellariumServer(
                self._pointing_state, goto_target=self._goto_target
            )
            self._stellarium.start()
        except Exception as exc:
            logger.error("Failed to start Stellarium server: %s", exc)
            self._stellarium = None

    def startup_lx200(self) -> None:
        """Start LX200 TCP server.

        Binds 0.0.0.0:4030 so mobile apps (SkySafari, Stellarium Mobile) can
        reach it on the LAN. Always-on; no config toggle in v1.
        """
        try:
            self._lx200 = Lx200Server(
                self._pointing_state,
                goto_target=self._goto_target,
                app_version=self._app_version,
            )
            self._lx200.start()
        except Exception as exc:
            logger.error("Failed to start LX200 server: %s", exc)
            self._lx200 = None

    def startup_webserver(self) -> None:
        """Start mobile web interface server."""
        try:
            self._webserver = WebServer(
                self._pointing_state,
                self._state_machine,
                self._goto_target,
                self._config,
                frame_buffer=self._frame_buffer,
                stellarium_object=lambda: self.stellarium_object,
                camera_controls=lambda: self.camera_controls,
                sync_state=lambda: {
                    "in_progress": self.sync_in_progress,
                    "candidates": [
                        {"idx": i, "name": f"Star #{i + 1}",
                         "ra_deg": c.ra, "dec_deg": c.dec, "magnitude": c.mag,
                         "pixel_x": c.x, "pixel_y": c.y}
                        for i, c in enumerate(self.sync_candidates or [])
                    ],
                    "selected_idx": self.sync_selected_idx,
                    "error": self.sync_error,
                },
                activity=lambda: {
                    "stellarium": {
                        "active": self.stellarium_has_client,
                        "address": self.stellarium_address,
                        "status": self.stellarium_status,
                        "object": self.stellarium_object,
                    },
                    "lx200": {
                        "active": self.lx200_active,
                        "address": self.lx200_address,
                    },
                    "webserver": {"url": self.web_url},
                    "audio_enabled": self.audio_enabled,
                },
                stellarium_location=lambda: (
                    (self.stellarium_status or {}).get("location")
                    if self.stellarium_status else None
                ),
                location=lambda: self.location,
                dev_mode=self._dev_mode,
                sample_active=lambda: self._sample_injector.active_name,
                actions=self,
            )
            self._webserver.start()
        except Exception as exc:
            logger.error("Failed to start web server: %s", exc)
            self._webserver = None

    @property
    def web_url(self) -> str | None:
        """LAN URL for the mobile web interface, or None if not running."""
        if self._webserver:
            return self._webserver.url
        return None

    def startup_camera(self) -> None:
        """Spawn camera subprocess, connect, handshake, restore settings.

        On first launch (config has no saved exposure/gain), each control is
        initialized to the midpoint of the range the camera reports — which
        differs by OS/camera backend, so we can't hardcode sensible defaults.
        """
        try:
            self._subprocess_mgr = SubprocessManager(
                self._frame_buffer, self._state_machine, self._config
            )
            hello = self._subprocess_mgr.start()
            logger.info("Camera connected: %s", hello)

            client = self._subprocess_mgr.client
            if client:
                for ctrl in client.controls:
                    cid = ctrl.get("id")
                    if cid not in ("exposure", "gain"):
                        continue
                    saved = self._config.exposure if cid == "exposure" else self._config.gain
                    if saved is None:
                        cmin = ctrl.get("min", 0)
                        cmax = ctrl.get("max", 0)
                        value = (cmin + cmax) // 2
                        logger.info(
                            "First-run %s = %d (midpoint of [%d, %d])",
                            cid, value, cmin, cmax,
                        )
                        if cid == "exposure":
                            self._config.exposure = value
                        else:
                            self._config.gain = value
                    else:
                        value = saved
                    client.set_control(cid, value)
                    client.update_cached_control(cid, value)
        except Exception as exc:
            logger.error("Failed to start camera: %s", exc)
            self._subprocess_mgr = None

    def retry_camera(self) -> bool:
        """Re-attempt camera startup on demand (e.g. user just plugged it in).

        Idempotent: if a camera is already connected, returns True without
        doing anything. Otherwise drops any stale SubprocessManager,
        re-runs startup_camera, and brings up the solver thread on success.
        Same code path as the initial boot, so the platform-specific risk
        surface (binary resolution, _kill_stale_server, Popen, handshake)
        is identical to what already runs once at every launch.
        Returns the post-attempt camera_connected state.
        """
        if self.camera_connected:
            return True
        # Drop the stale manager so startup_camera builds a fresh one;
        # _kill_stale_server inside SubprocessManager._spawn_process will
        # reap any orphaned camera_server left over from the prior failure.
        self._subprocess_mgr = None
        self.startup_camera()
        if self.camera_connected and self._solver_thread is None:
            self.startup_solver_thread()
        return self.camera_connected

    def startup_solver_thread(self) -> None:
        """Create solver thread object (not started until user enables tracking)."""
        if self._solver:
            self._audio = AudioAlert(enabled=self._config.audio_enabled)
            self._solver_thread = SolverThread(
                self._solver,
                self._frame_buffer,
                self._pointing_state,
                self._state_machine,
                self._config,
                audio=self._audio,
            )
            # Wire solver failure count into web server for audio event detection
            if self._webserver is not None:
                self._webserver._solver_failures = lambda: self.consecutive_failures

    # -- tracking lifecycle (§8.3) --------------------------------------------

    def skip_calibration(self) -> None:
        """Skip finder rotation calibration, proceed to tracking."""
        if self._state_machine.state == EngineState.CALIBRATE:
            if self._solver_thread:
                self._solver_thread.skip_calibrate()

    def use_previous_calibration(self) -> None:
        """Restore saved sync + finder rotation from config and start tracking.

        Only valid from SYNC state when config has saved calibration data.
        """
        if not self.camera_connected:
            logger.info("use_previous_calibration ignored — camera not connected")
            return
        if self._state_machine.state != EngineState.SYNC:
            return
        if not self._config.has_calibration:
            return
        if not self._solver_thread:
            logger.error("No solver thread available")
            return
        d_body = np.array(self._config.sync_d_body)
        self._solver_thread.set_sync_d_body(d_body)
        logger.info(
            "Using previous calibration: d_body=(%.6f, %.6f, %.6f) "
            "finder_rotation=%.1f°",
            d_body[0], d_body[1], d_body[2],
            self._config.finder_rotation,
        )
        self._solver_thread.start()  # SYNC → WARMING_UP

    def step_advance(self) -> None:
        """Advance the wizard: SETUP → SYNC → SYNC_CONFIRM → CALIBRATE → WARMING_UP, or stop."""
        state = self._state_machine.state
        logger.info("step_advance called, state=%s", state.value)
        # Every forward step needs camera frames. Only the "stop tracking"
        # branch (WARMING_UP/TRACKING → SETUP) works without a camera.
        if not self.camera_connected and state not in (
            EngineState.WARMING_UP, EngineState.TRACKING,
        ):
            logger.info("step_advance ignored — camera not connected")
            return
        if state == EngineState.SETUP:
            self._state_machine.transition(EngineState.SYNC)
        elif state == EngineState.SYNC:
            if not self._solver:
                logger.error("No solver available")
                return
            if not self._sync_lock.acquire(blocking=False):
                return  # solve already in progress
            self._sync_error = None
            threading.Thread(
                target=self._perform_sync_solve, name="sync-solve", daemon=True
            ).start()
        elif state == EngineState.SYNC_CONFIRM:
            self._confirm_sync()
        elif state == EngineState.CALIBRATE:
            self.skip_calibration()
        elif state in (EngineState.WARMING_UP, EngineState.TRACKING):
            if self._solver_thread:
                self._solver_thread.stop()
                self._solver_thread.set_sync_d_body(None)
            self._clear_sync_data()
            state = self._state_machine.state
            if state in (EngineState.WARMING_UP, EngineState.TRACKING):
                self._state_machine.transition(EngineState.SETUP)

    # -- two-phase sync -------------------------------------------------------

    def _perform_sync_solve(self) -> None:
        """Background thread: solve frame, build candidates, transition to SYNC_CONFIRM."""
        try:
            frame_data, _, _ = self._frame_buffer.get()
            if frame_data is None:
                self._sync_error = "No camera frame available"
                return
            result = self._solver.solve_frame(frame_data)
            if not PlateSolver.is_valid(
                result, self._config.min_matches, self._config.max_prob
            ):
                self._sync_error = (
                    "Plate solve failed \u2014 ensure stars are visible and retry"
                )
                return
            candidates = build_sync_candidates(
                result["matched_centroids"],
                result["matched_stars"],
                result["image_size"],
            )
            if not candidates:
                self._sync_error = (
                    "No suitable stars found \u2014 adjust framing and retry"
                )
                return
            self._sync_candidates = candidates
            self._sync_selected_idx = auto_select(candidates, result["image_size"])
            self._sync_camera_ra = result["RA"]
            self._sync_camera_dec = result["Dec"]
            self._sync_camera_roll = result["Roll"]
            self._state_machine.transition(EngineState.SYNC_CONFIRM)
        except Exception as exc:
            logger.error("Sync solve failed: %s", exc)
            self._sync_error = str(exc)
        finally:
            self._sync_lock.release()

    def _confirm_sync(self) -> None:
        """Compute body-frame sync from single point and start calibration."""
        if not self._sync_candidates or self._sync_selected_idx is None:
            return
        if not self._solver_thread:
            logger.error("No solver thread available")
            return
        target = self._sync_candidates[self._sync_selected_idx]
        d_body = compute_body_frame_sync(
            self._sync_camera_ra,
            self._sync_camera_dec,
            self._sync_camera_roll,
            target.ra,
            target.dec,
        )
        logger.info(
            "Body-frame sync: cam=(%.4f, %.4f, roll=%.1f) "
            "target=(%.4f, %.4f) star_mag=%.1f d_body=(%.6f, %.6f, %.6f)",
            self._sync_camera_ra, self._sync_camera_dec, self._sync_camera_roll,
            target.ra, target.dec, target.mag,
            d_body[0], d_body[1], d_body[2],
        )
        self._solver_thread.set_sync_d_body(d_body)
        self._config.sync_d_body = d_body.tolist()
        self._solver_thread.start_calibrate(
            self._sync_camera_ra,
            self._sync_camera_dec,
            self._sync_camera_roll,
        )  # SYNC_CONFIRM → CALIBRATE

    def sync_retry(self) -> None:
        """Go back to SYNC to redo the current solve (preserves earlier pairs)."""
        if self._state_machine.state == EngineState.SYNC_CONFIRM:
            self._sync_candidates = None
            self._sync_selected_idx = None
            self._sync_error = None
            self._state_machine.transition(EngineState.SYNC)

    def set_sync_selected(self, idx: int) -> None:
        """Called by UI when user taps a candidate."""
        if self._sync_candidates and 0 <= idx < len(self._sync_candidates):
            self._sync_selected_idx = idx

    def _clear_sync_data(self) -> None:
        self._sync_candidates = None
        self._sync_selected_idx = None
        self._sync_error = None

    @property
    def sync_candidates(self) -> list[SyncCandidate] | None:
        return self._sync_candidates

    @property
    def sync_selected_idx(self) -> int | None:
        return self._sync_selected_idx

    @property
    def sync_error(self) -> str | None:
        return self._sync_error

    @property
    def sync_in_progress(self) -> bool:
        return self._sync_lock.locked()

    # -- camera control (§8.4) ------------------------------------------------

    def set_control(self, control_id: str, value: int) -> None:
        """Send a camera control change and persist to config."""
        client = self._subprocess_mgr.client if self._subprocess_mgr else None
        if client:
            client.set_control(control_id, value)
        # Persist to config
        if control_id == "exposure":
            self._config.exposure = value
        elif control_id == "gain":
            self._config.gain = value

    # -- shutdown (§8.5) ------------------------------------------------------

    def shutdown(self) -> None:
        """Graceful shutdown. Each step with independent timeout."""
        logger.info("Shutting down")

        # 0. Stop sample injector (so it stops writing frames before solver stops)
        try:
            self._sample_injector.stop()
        except Exception as exc:
            logger.error("Error stopping sample injector: %s", exc)

        # 1. Stop solver thread
        if self._solver_thread:
            try:
                self._solver_thread.stop(timeout=2)
            except Exception as exc:
                logger.error("Error stopping solver: %s", exc)

        # 2. Stop Stellarium server
        if self._stellarium:
            try:
                self._stellarium.stop(timeout=2)
            except Exception as exc:
                logger.error("Error stopping Stellarium: %s", exc)

        # 2b. Stop LX200 server
        if self._lx200:
            try:
                self._lx200.stop(timeout=2)
            except Exception as exc:
                logger.error("Error stopping LX200 server: %s", exc)

        # 3a. Stop web server
        if self._webserver:
            try:
                self._webserver.stop(timeout=2)
            except Exception as exc:
                logger.error("Error stopping web server: %s", exc)

        # 3. Terminate camera subprocess
        if self._subprocess_mgr:
            try:
                self._subprocess_mgr.stop()
            except Exception as exc:
                logger.error("Error stopping camera: %s", exc)

        # 4. Save config
        try:
            self._config.save()
        except Exception as exc:
            logger.error("Error saving config: %s", exc)

        # 5. Flush logs
        logger.info("Shutdown complete")
        logging.shutdown()

    # -- internal -------------------------------------------------------------

    def _log_version(self) -> None:
        try:
            with open(_VERSION_PATH) as f:
                version = json.load(f)
            logger.info("EVF version: %s", version)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Could not read VERSION.json: %s", exc)
