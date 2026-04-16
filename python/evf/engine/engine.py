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

import json
import logging
import threading

from evf.camera.subprocess_mgr import SubprocessManager
from evf.config.logging_setup import setup_logging
from evf.config.manager import ConfigManager
from evf.engine.audio import AudioAlert
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import EngineState, StateMachine
from evf.solver.solver import PlateSolver
import numpy as np

from evf.solver.sync import (
    SyncCandidate,
    auto_select,
    build_sync_candidates,
    compute_body_frame_sync,
)
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

    def __init__(self) -> None:
        # Shared data structures
        self._frame_buffer = LatestFrame()
        self._pointing_state = PointingState()
        self._state_machine = StateMachine()
        self._config = ConfigManager()
        self._goto_target = GotoTarget()
        self._app_version = _read_app_version()

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

    # -- startup (§8.2) -------------------------------------------------------

    def startup_logging(self) -> None:
        """Initialize logging and log version info."""
        setup_logging(verbose=self._config.verbose, console=True)
        logger.info("EVF starting up")
        self._log_version()

    def startup_solver(self) -> None:
        """Load tetra3 database (~2-5s)."""
        try:
            self._solver = PlateSolver()
        except Exception as exc:
            logger.error("Failed to load tetra3 database: %s", exc)

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
                stellarium_object=lambda: self.stellarium_object,
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
        """Spawn camera subprocess, connect, handshake, restore settings."""
        try:
            self._subprocess_mgr = SubprocessManager(
                self._frame_buffer, self._state_machine, self._config
            )
            hello = self._subprocess_mgr.start()
            logger.info("Camera connected: %s", hello)

            client = self._subprocess_mgr.client
            if client:
                client.set_control("exposure", self._config.exposure)
                client.set_control("gain", self._config.gain)
        except Exception as exc:
            logger.error("Failed to start camera: %s", exc)
            self._subprocess_mgr = None

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
