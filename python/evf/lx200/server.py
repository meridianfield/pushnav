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

"""LX200 TCP server - request/response, multi-client.

Mirrors StellariumServer architecture but:
  - request/response only (no periodic broadcast)
  - per-client state (precision, pending target, recv buffer)
  - ASCII '#'-terminated framing
  - binds 0.0.0.0 by default (LAN reach for mobile apps)
"""

import logging
import select
import socket
import threading

from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.lx200.protocol import Lx200ClientState, Lx200Context, dispatch
from evf.paths import sounds_dir

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "0.0.0.0"    # LAN-reachable - LX200 clients include mobile apps
_DEFAULT_PORT = 4030          # SkyFi/SkySafari convention
_SELECT_POLL_INTERVAL = 0.1   # seconds - snappy response to commands
_MAX_RECV_BUFFER = 4096       # bytes - trim oldest half and WARN if exceeded

_SOUNDS_DIR = sounds_dir()
_ACK_SOUND = _SOUNDS_DIR / "goto_ack.wav"

_playsound = None
try:
    from playsound3 import playsound as _playsound
except ImportError:
    pass


def _play_ack() -> None:
    """Play the ack sound. Non-blocking. Never raises.

    NOTE: GotoTarget.set() already plays this sound internally, so the
    LX200 dispatch path does NOT call play_ack on :MS#. This hook exists
    for future use (e.g. different sounds for :CM# if that policy changes).
    """
    if _playsound is None:
        return
    try:
        _playsound(str(_ACK_SOUND), block=False)
    except Exception as exc:
        logger.debug("LX200 ack sound failed: %s", exc)


class Lx200Server:
    """TCP server speaking LX200 Classic to SkySafari / Stellarium Mobile /
    INDI lx200basic / ASCOM Meade Generic.

    Runs in a dedicated daemon thread. Accepts multiple clients.
    Pure request/response - never emits unsolicited bytes.
    """

    def __init__(
        self,
        pointing: PointingState,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        goto_target: GotoTarget | None = None,
        app_version: str = "0.0.0",
    ) -> None:
        self._host = host
        self._port = port
        self._ctx = Lx200Context(
            pointing=pointing,
            goto_target=goto_target,
            play_ack=_play_ack,
            app_version=app_version,
        )
        self._clients: dict[socket.socket, Lx200ClientState] = {}
        self._server_sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._stop_event.clear()
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen(5)
        self._server_sock.setblocking(False)
        logger.info("LX200 server listening on %s:%d", self._host, self.port)

        self._thread = threading.Thread(target=self._run, name="lx200", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._cleanup()
        logger.info("LX200 server stopped")

    @property
    def port(self) -> int:
        """Actual bound port (useful when port=0 for tests)."""
        if self._server_sock is not None:
            return self._server_sock.getsockname()[1]
        return self._port

    # -- internal -------------------------------------------------------------

    def _run(self) -> None:
        assert self._server_sock is not None
        while not self._stop_event.is_set():
            readable = [self._server_sock] + list(self._clients.keys())
            try:
                ready, _, _ = select.select(readable, [], [], _SELECT_POLL_INTERVAL)
            except (OSError, ValueError):
                # A client closed underneath us; next iteration rebuilds the list
                continue

            for sock in ready:
                if sock is self._server_sock:
                    self._accept_new_client()
                else:
                    self._handle_client_data(sock)

    def _accept_new_client(self) -> None:
        assert self._server_sock is not None
        try:
            client, addr = self._server_sock.accept()
        except OSError:
            return
        client.setblocking(False)
        self._clients[client] = Lx200ClientState()
        logger.info("LX200 client connected from %s:%d", *addr)

    def _handle_client_data(self, client: socket.socket) -> None:
        state = self._clients.get(client)
        if state is None:
            return
        try:
            data = client.recv(1024)
        except (ConnectionResetError, BrokenPipeError, OSError):
            self._remove_client(client)
            return
        if not data:
            self._remove_client(client)
            return

        state.recv_buffer += data

        # Defensive: cap buffer to avoid unbounded growth from misbehaving clients.
        # LX200 commands start with ':' - resync by discarding everything before
        # the most recent ':' (or dropping the whole buffer if no ':' is present).
        if len(state.recv_buffer) > _MAX_RECV_BUFFER:
            logger.warning("LX200 recv buffer overflow, resyncing on next ':'")
            last_colon = state.recv_buffer.rfind(b":")
            if last_colon == -1:
                state.recv_buffer = b""
            else:
                state.recv_buffer = state.recv_buffer[last_colon:]

        # Process every '#'-terminated command in the buffer
        while b"#" in state.recv_buffer:
            cmd, _, rest = state.recv_buffer.partition(b"#")
            state.recv_buffer = rest
            # Strip stray leading whitespace / control bytes (some clients send
            # ACK 0x06 probes; Meade Generic sends :<cmd># cleanly)
            cmd = cmd.lstrip(b"\x00 \r\n\t\x06")
            if not cmd:
                continue
            try:
                reply = dispatch(cmd, state, self._ctx)
            except Exception as exc:
                logger.exception("LX200 dispatch error for %r: %s", cmd, exc)
                reply = None
            if reply is not None:
                try:
                    client.sendall(reply)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    self._remove_client(client)
                    return

    def _remove_client(self, client: socket.socket) -> None:
        try:
            peer = client.getpeername()
            logger.info("LX200 client disconnected: %s:%d", *peer)
        except OSError:
            logger.info("LX200 client disconnected")
        try:
            client.close()
        except OSError:
            pass
        self._clients.pop(client, None)

    def _cleanup(self) -> None:
        for client in list(self._clients.keys()):
            try:
                client.close()
            except OSError:
                pass
        self._clients.clear()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
