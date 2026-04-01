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

"""Stellarium TCP server — broadcasts pointing position at ~1 Hz."""

import json
import logging
import select
import socket
import struct
import threading
from urllib.error import URLError
from urllib.request import Request, urlopen

from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.paths import sounds_dir
from evf.stellarium.protocol import _GOTO_LEN, decode_goto, encode_position

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_SOUNDS_DIR = sounds_dir()
_ACK_SOUND = _SOUNDS_DIR / "goto_ack.wav"

_playsound = None
try:
    from playsound3 import playsound as _playsound
except ImportError:
    pass
_DEFAULT_PORT = 10001
_BROADCAST_INTERVAL = 1.0  # seconds


def _play_ack() -> None:
    """Play acknowledgment sound. Non-blocking, never raises."""
    if _playsound is None:
        return
    try:
        _playsound(str(_ACK_SOUND), block=False)
    except Exception as exc:
        logger.debug("Connect ack sound failed: %s", exc)


class StellariumServer:
    """TCP server that broadcasts RA/Dec to connected Stellarium clients.

    Runs in a dedicated daemon thread. Accepts multiple clients.
    Sends position updates at ~1 Hz when PointingState is valid.
    Reads and logs (but ignores) incoming GOTO commands.
    """

    def __init__(
        self,
        pointing: PointingState,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        goto_target: GotoTarget | None = None,
    ) -> None:
        self._pointing = pointing
        self._host = host
        self._port = port
        self._goto_target = goto_target
        self._rc_port: int = 8090
        self._stellarium_status: dict | None = None
        self._stellarium_object: dict | None = None
        self._clients: list[socket.socket] = []
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
        logger.info("Stellarium server listening on %s:%d", self._host, self._port)

        self._thread = threading.Thread(target=self._run, name="stellarium", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._cleanup()
        logger.info("Stellarium server stopped")

    @property
    def port(self) -> int:
        """Return the actual bound port (useful when port=0 for tests)."""
        if self._server_sock is not None:
            return self._server_sock.getsockname()[1]
        return self._port

    @property
    def stellarium_status(self) -> dict | None:
        return self._stellarium_status

    @property
    def stellarium_object(self) -> dict | None:
        return self._stellarium_object

    # -- internal -------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._accept_new_clients()
            self._read_gotos()
            self._broadcast()
            self._stop_event.wait(_BROADCAST_INTERVAL)

    def _accept_new_clients(self) -> None:
        assert self._server_sock is not None
        while True:
            try:
                readable, _, _ = select.select([self._server_sock], [], [], 0)
                if not readable:
                    break
                client, addr = self._server_sock.accept()
                client.setblocking(False)
                self._clients.append(client)
                logger.info("Stellarium client connected from %s:%d", *addr)
                _play_ack()
                threading.Thread(
                    target=self._fetch_stellarium_status,
                    name="stellarium-rc-status",
                    daemon=True,
                ).start()
            except OSError:
                break

    def _read_gotos(self) -> None:
        for client in self._clients[:]:
            try:
                readable, _, _ = select.select([client], [], [], 0)
                if not readable:
                    continue
                data = client.recv(1024)
                if not data:
                    self._remove_client(client)
                    continue
                # Parse 20-byte GOTO messages
                while len(data) >= _GOTO_LEN:
                    chunk = data[:_GOTO_LEN]
                    data = data[_GOTO_LEN:]
                    try:
                        ra_h, dec_d = decode_goto(chunk)
                        if self._goto_target is not None:
                            self._goto_target.set(ra_h * 15.0, dec_d)
                        logger.info(
                            "Stellarium GOTO received: RA=%.4fh Dec=%.4f°",
                            ra_h,
                            dec_d,
                        )
                        threading.Thread(
                            target=self._fetch_goto_details,
                            args=(ra_h * 15.0, dec_d),
                            name="stellarium-rc-goto",
                            daemon=True,
                        ).start()
                    except struct.error:
                        logger.debug("Malformed GOTO message, skipping")
            except (ConnectionResetError, BrokenPipeError, OSError):
                self._remove_client(client)

    def _broadcast(self) -> None:
        snap = self._pointing.read()
        if not snap.valid:
            return

        # PointingState stores RA in degrees; Stellarium protocol wants hours
        ra_hours = snap.ra_j2000 / 15.0
        msg = encode_position(ra_hours, snap.dec_j2000)

        for client in self._clients[:]:
            try:
                client.sendall(msg)
            except (ConnectionResetError, BrokenPipeError, OSError):
                self._remove_client(client)

    def _remove_client(self, client: socket.socket) -> None:
        try:
            peer = client.getpeername()
            logger.info("Stellarium client disconnected: %s:%d", *peer)
        except OSError:
            logger.info("Stellarium client disconnected")
        try:
            client.close()
        except OSError:
            pass
        if client in self._clients:
            self._clients.remove(client)

    def _fetch_stellarium_status(self) -> None:
        """Query Stellarium Remote Control for observer status. Best-effort."""
        url = f"http://localhost:{self._rc_port}/api/main/status"
        try:
            with urlopen(Request(url), timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._stellarium_status = data
            logger.debug("Stellarium status (raw): %s", json.dumps(data, indent=2))
            loc = data.get("location", {})
            time_info = data.get("time", {})
            view = data.get("view", {})
            logger.info(
                "Stellarium status: %s, %s (lat=%.4f, lon=%.4f, alt=%.0f) "
                "tz=%s fov=%.2f°",
                loc.get("name", "?"),
                loc.get("country", "?"),
                loc.get("latitude", 0),
                loc.get("longitude", 0),
                loc.get("altitude", 0),
                time_info.get("timeZone", "?"),
                view.get("fov", 0),
            )
        except (URLError, OSError, ValueError) as exc:
            logger.debug("Stellarium Remote Control unavailable: %s", exc)

    def _fetch_goto_details(self, ra_deg: float, dec_deg: float) -> None:
        """Query object details and refresh status after GOTO. Best-effort."""
        base = f"http://localhost:{self._rc_port}"
        # 1. Object info
        try:
            with urlopen(Request(f"{base}/api/objects/info?format=json"), timeout=2.0) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
            self._stellarium_object = obj
            logger.debug("Stellarium object (raw): %s", json.dumps(obj, indent=2))
            name = obj.get("localized-name") or obj.get("name", "?")
            logger.info(
                "Stellarium object: %s (type=%s, vmag=%.2f, "
                "RA=%s Dec=%s, constellation=%s)",
                name,
                obj.get("object-type", "?"),
                obj.get("vmag", 0),
                obj.get("raJ2000", "?"),
                obj.get("decJ2000", "?"),
                obj.get("constellation-short", "?"),
            )
        except (URLError, OSError, ValueError) as exc:
            logger.debug("Could not fetch object info: %s", exc)

        # 2. Refresh status
        self._fetch_stellarium_status()

    def _cleanup(self) -> None:
        for client in self._clients[:]:
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
