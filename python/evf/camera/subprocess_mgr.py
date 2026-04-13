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

"""Camera subprocess manager — spawn, monitor, and recover the camera server.

Per specs/start/impl0.md §Phase 5.
"""

import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from evf.camera.client import CameraClient
from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.state import EngineState, StateMachine

logger = logging.getLogger(__name__)


class SubprocessManager:
    """Manage the camera server subprocess lifecycle.

    Spawns the Swift camera_server binary, connects a CameraClient,
    monitors the connection, and performs crash recovery with backoff.
    """

    _BACKOFF = [1, 2, 4, 8, 15]
    _MONITOR_INTERVAL = 0.5
    _PORT_POLL_INTERVAL = 0.1
    _PORT_TIMEOUT = 15.0
    _FRAME_STALL_TIMEOUT = 2.0

    def __init__(
        self,
        frame_buffer: LatestFrame,
        state_machine: StateMachine,
        config: ConfigManager,
        binary_path: str | Path | None = None,
        host: str = "127.0.0.1",
        port: int = 8764,
    ) -> None:
        self._frame_buffer = frame_buffer
        self._state_machine = state_machine
        self._config = config
        self._binary_path: Path = self._resolve_binary(binary_path)
        self._host = host
        self._port = port
        self._process: subprocess.Popen | None = None
        self._client: CameraClient | None = None
        self._monitor_thread: threading.Thread | None = None
        self._recovery_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._recovering = False

    # -- public API -----------------------------------------------------------

    def start(self) -> dict:
        """Spawn the camera server, connect, handshake, and start receiving.

        Returns the HELLO info dict from the camera server.
        Raises RuntimeError if the server fails to start or connect.
        """
        self._stop_event.clear()
        self._spawn_process()
        hello = self._connect_with_retry()
        self._client.start_receiving()
        self._start_monitor()
        return hello

    def stop(self) -> None:
        """Stop the camera server and clean up all resources."""
        self._stop_event.set()
        # Wait for recovery thread to notice the stop event
        if self._recovery_thread is not None and self._recovery_thread.is_alive():
            self._recovery_thread.join(timeout=max(self._BACKOFF) + 5)
        # Wait for monitor thread
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        self._monitor_thread = None
        self._recovery_thread = None
        self._cleanup_client()
        self._terminate_process()

    @property
    def client(self) -> CameraClient | None:
        return self._client

    @property
    def running(self) -> bool:
        return self._client is not None and self._client.connected

    # -- binary resolution ----------------------------------------------------

    @staticmethod
    def _resolve_binary(binary_path: str | Path | None) -> Path:
        if binary_path is not None:
            return Path(binary_path)
        from evf.paths import camera_binary
        return camera_binary()

    # -- spawn / terminate ----------------------------------------------------

    def _kill_stale_server(self) -> None:
        """Kill any leftover camera_server process from a previous run.

        If PushNav was force-quit or crashed, the camera server may still
        be alive holding the camera device and TCP port.  This prevents
        the new instance from connecting.
        """
        name = Path(self._binary_path).name
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/IM", name],
                    capture_output=True, timeout=5,
                )
            else:
                subprocess.run(
                    ["pkill", "-f", name],
                    capture_output=True, timeout=5,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        # Brief pause to let the OS release the port
        time.sleep(0.5)

    def _spawn_process(self) -> None:
        self._kill_stale_server()
        path = str(self._binary_path)
        cmd = [sys.executable, path] if path.endswith(".py") else [path]
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs,
        )
        logger.info(
            "Spawned camera server (PID %d): %s",
            self._process.pid,
            self._binary_path,
        )

    def _connect_with_retry(self) -> dict:
        """Retry CameraClient.connect() until the server is ready.

        The camera server may take a few seconds to bind after spawning
        (AVFoundation + UVC init).  We must NOT probe the port with a
        bare TCP connect because the Swift server exits when any client
        disconnects.  Instead, retry the real CameraClient handshake.
        """
        self._frame_buffer.clear()  # reset so new client's frame_ids are accepted
        deadline = time.monotonic() + self._PORT_TIMEOUT
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            # Bail early if the server process already exited
            if self._process is not None and self._process.poll() is not None:
                rc = self._process.returncode
                stderr_text = ""
                try:
                    _, stderr_bytes = self._process.communicate(timeout=1)
                    if stderr_bytes:
                        stderr_text = stderr_bytes.decode(errors="replace").strip()
                except (subprocess.TimeoutExpired, ValueError):
                    pass
                self._process = None
                msg = (
                    f"Camera server exited immediately (rc={rc}). "
                    f"Stderr: {stderr_text or '(empty)'}"
                )
                logger.error(msg)
                raise RuntimeError(msg)
            try:
                self._client = CameraClient(
                    self._frame_buffer, self._host, self._port
                )
                return self._client.connect(timeout=1.0)
            except Exception as exc:
                last_exc = exc
                self._client = None
                time.sleep(self._PORT_POLL_INTERVAL)
        raise RuntimeError(
            f"Camera server not listening on {self._host}:{self._port} "
            f"within {self._PORT_TIMEOUT}s: {last_exc}"
        )

    def _cleanup_client(self) -> None:
        if self._client is not None:
            self._client.stop()
            self._client = None

    def _terminate_process(self) -> None:
        proc = self._process
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            logger.warning("Camera server did not exit after SIGTERM, sending SIGKILL")
            proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=1)
            if stdout:
                logger.debug("Camera stdout: %s", stdout.decode(errors="replace"))
            if stderr:
                logger.debug("Camera stderr: %s", stderr.decode(errors="replace"))
        except (subprocess.TimeoutExpired, ValueError):
            pass
        self._process = None

    # -- monitor --------------------------------------------------------------

    def _start_monitor(self) -> None:
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="camera-monitor", daemon=True
        )
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._stop_event.wait(self._MONITOR_INTERVAL):
                return
            client = self._client
            if client is None or self._stop_event.is_set() or self._recovering:
                continue
            # Detect TCP disconnect
            if not client.connected:
                logger.warning("Camera disconnected — starting recovery")
                self._start_recovery()
                return
            # Detect frame stall (socket open but no frames arriving)
            if client.last_frame_time > 0:
                stall = time.monotonic() - client.last_frame_time
                if stall > self._FRAME_STALL_TIMEOUT:
                    logger.warning(
                        "No frames for %.1fs — treating as stall, starting recovery",
                        stall,
                    )
                    self._start_recovery()
                    return

    # -- crash recovery -------------------------------------------------------

    def _start_recovery(self) -> None:
        self._recovering = True
        self._state_machine.transition(EngineState.RECONNECTING)
        self._recovery_thread = threading.Thread(
            target=self._recovery_loop, name="camera-recovery", daemon=True
        )
        self._recovery_thread.start()

    def _recovery_loop(self) -> None:
        try:
            for i, delay in enumerate(self._BACKOFF):
                logger.info(
                    "Recovery attempt %d/%d in %ss",
                    i + 1,
                    len(self._BACKOFF),
                    delay,
                )
                if self._stop_event.wait(delay):
                    logger.info("Recovery cancelled by stop()")
                    return
                try:
                    self._cleanup_client()
                    self._terminate_process()
                    if self._stop_event.is_set():
                        return
                    self._spawn_process()
                    self._connect_with_retry()
                    self._client.start_receiving()
                    # Restore camera settings from config
                    if self._config.exposure is not None:
                        self._client.set_control("exposure", self._config.exposure)
                    if self._config.gain is not None:
                        self._client.set_control("gain", self._config.gain)
                    self._state_machine.transition(EngineState.SETUP)
                    logger.info("Recovery succeeded on attempt %d", i + 1)
                    self._start_monitor()
                    return
                except Exception as exc:
                    logger.warning(
                        "Recovery attempt %d/%d failed: %s",
                        i + 1,
                        len(self._BACKOFF),
                        exc,
                    )
            logger.error(
                "Camera recovery failed after %d attempts", len(self._BACKOFF)
            )
            self._state_machine.transition(EngineState.ERROR)
        finally:
            self._recovering = False
