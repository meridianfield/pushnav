"""WebServer.stop() with live clients: clean, fast, and frees the port."""

import asyncio
import logging
import socket
import threading
import time

import aiohttp

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver.server import WebServer

_TINY_JPEG = b"\xff\xd8\xff\xd9"


def _start_server(tmp_path) -> WebServer:
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    cfg._data["webserver"]["port"] = 0  # ephemeral
    fb = LatestFrame()
    fb.set(_TINY_JPEG, time.time(), 1)
    ws = WebServer(PointingState(), StateMachine(), GotoTarget(), cfg, frame_buffer=fb)
    ws.start()
    for _ in range(40):
        if ws._port is not None:
            break
        time.sleep(0.05)
    assert ws._port is not None, "Web server did not bind in time"
    return ws


def _hold_clients(port: int, connected: threading.Event, closed: dict) -> None:
    """Open a /ws client and a /frame.mjpg stream, then wait for the server to drop them."""

    async def run() -> None:
        async with aiohttp.ClientSession() as s:
            ws = await s.ws_connect(f"http://127.0.0.1:{port}/ws")
            mjpeg = await s.get(f"http://127.0.0.1:{port}/frame.mjpg")
            await mjpeg.content.readany()  # stream is live
            connected.set()
            msg = await ws.receive(timeout=10)
            closed["ws"] = msg.type
            mjpeg.close()

    asyncio.run(run())


def test_stop_with_live_clients_is_clean(tmp_path, caplog):
    server = _start_server(tmp_path)
    port = server._port
    connected, closed = threading.Event(), {}
    client = threading.Thread(target=_hold_clients, args=(port, connected, closed))
    client.start()
    assert connected.wait(5), "clients did not connect"

    with caplog.at_level(logging.INFO, logger="evf.webserver.server"):
        t0 = time.monotonic()
        server.stop(timeout=3)
        elapsed = time.monotonic() - t0

    assert not server._thread.is_alive()
    assert elapsed < 2.0
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    client.join(timeout=5)
    assert closed.get("ws") in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)

    # Port is released: a new listener can bind it straight away.
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", port))
