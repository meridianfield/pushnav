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

"""EVF — Electronic Viewfinder main entry point.

Per impl0.md §8.6.
"""

import json
import logging
import os
import signal
import socket
import sys
import threading
import urllib.error
import urllib.request

from evf.config.manager import ConfigManager
from evf.engine.engine import Engine

logger = logging.getLogger(__name__)

# Window dimensions sized to the React UI's `max-w-5xl` (1024px) layout
# plus minimal padding. The window is non-resizable (see `resizable=False`
# in create_window below) so the layout never has to deal with arbitrary
# aspect ratios — the dome, controls and panels are all designed around
# this single size.
# Each platform's webview (WKWebView / WebKit2GTK / WebView2) handles HiDPI
# scaling natively against its OS's DPI/scale settings — no app-side multiplier.
_VP_WIDTH = 1060
_VP_HEIGHT = 820


def _vite_running(port: int = 5173) -> bool:
    """True if **PushNav's** Vite dev server is reachable on localhost:`port`.

    A bare TCP probe isn't enough (the port can be squatted on — macOS uses
    5000 for AirPlay Receiver, for instance) and a generic Vite marker
    like `/@vite/client` would also succeed against an *unrelated* Vite
    running someone else's project. Probe a PushNav-specific public asset
    instead: `web/public/inapp-title.png` is served at
    `/static/inapp-title.png` because of `vite.config.ts`'s
    `base: "/static/"`. A foreign Vite (default base `"/"`) 404s the path
    so we correctly fall through to the prod URL on :8765.
    """
    # Use `localhost` (not 127.0.0.1) so the OS resolver tries both ::1 and
    # 127.0.0.1 — Vite on macOS binds IPv6-only by default, while other
    # platforms or `--host` bind IPv4. urllib walks the address list until
    # one succeeds, so a single probe covers both families.
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/static/inapp-title.png", timeout=0.3
        ) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _check_single_instance(port: int) -> None:
    """Exit cleanly if another PushNav (or anything) is already on `port`.

    Runs before any engine threads, port binds, or pywebview windows
    open. Distinguishes "another PushNav" from "another app on the
    port" by hitting our /api/version identifier endpoint, so the
    error message can tell the user what to do.
    """
    # Fast TCP probe first — if the port is free, the slow HTTP probe
    # would just time out. Use 127.0.0.1 explicitly: webserver binds
    # 0.0.0.0 so this always reaches our listener if any.
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            pass  # something is bound
    except OSError:
        return  # port free, fine to start

    # Port is busy. Identify the occupant.
    is_pushnav = False
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/version", timeout=0.5
        ) as r:
            if r.status == 200:
                payload = json.loads(r.read(512))
                is_pushnav = payload.get("app") == "pushnav"
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
        pass

    if is_pushnav:
        msg = (
            f"PushNav is already running on port {port}.\n"
            f"Close the existing window before launching another instance."
        )
    else:
        msg = (
            f"Port {port} is in use by another application.\n"
            f"Close it, or change webserver.port in your PushNav config "
            f"(see logs for the config file location)."
        )
    print(msg, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    # PUSHNAV_DEBUG=1 is equivalent to --dev (engine dev features +
    # WebKit inspector) on every platform.
    dev_mode = "--dev" in sys.argv or os.environ.get("PUSHNAV_DEBUG") == "1"
    no_window = "--no-window" in sys.argv
    # --react is now the default; accept the flag as a no-op for back-compat
    _ = "--react" in sys.argv

    # Single-instance guard. Reads config first (we need web_port for the
    # probe) and reuses the same ConfigManager for the engine, so it isn't
    # loaded twice from disk.
    config = ConfigManager()
    _check_single_instance(config.web_port)

    engine = Engine(dev_mode=dev_mode, config=config)

    # Engine + servers come up either way
    engine.startup_logging()
    engine.startup_solver()
    engine.startup_stellarium()
    engine.startup_lx200()
    engine.startup_webserver()
    engine.startup_camera()
    if engine.camera_connected:
        engine.startup_solver_thread()

    if no_window:
        logger.info("Running headless (--no-window). Press Ctrl-C to exit.")
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        stop.wait()
        engine.shutdown()
        return

    # Default: open pywebview window pointing at the React UI
    import webview

    # Use Vite's HMR server when it's actually running; otherwise serve the
    # prebuilt bundle through the in-process aiohttp server. The prod URL
    # is built from engine.config.web_port (single source of truth) so a
    # user-customized port keeps the navigation URL and the bound webserver
    # in sync — and old config files carried over from earlier installs
    # don't desync the two sides.
    web_port = engine.config.web_port
    # Append a per-launch cache-buster to the entry URL. WKWebView keeps a
    # persistent HTTP cache under ~/Library/Caches/com.pushnav.evf and
    # aiohttp's FileResponse sends no Cache-Control, so heuristic freshness
    # can keep serving a stale index.html past Cmd-Q + restart and the
    # webview keeps booting an old JS bundle. A unique query per launch
    # makes the URL miss any prior cache entry.
    import time as _time
    cache_buster = f"?v={int(_time.time())}"
    target_url = (
        f"http://localhost:5173{cache_buster}" if _vite_running()
        else f"http://localhost:{web_port}/{cache_buster}"
    )
    title = f"PushNav {engine.app_version}"

    webview.create_window(
        title,
        target_url,
        width=_VP_WIDTH,
        height=_VP_HEIGHT,
        resizable=False,
    )
    # On Linux, force pywebview's Qt backend (QtPy + PyQt6 + PyQt6-WebEngine,
    # pulled in by the pywebview[qt] extra in pyproject.toml). Without this,
    # pywebview probes GTK first and only falls through to Qt on ImportError —
    # works either way, but `gui='qt'` skips the noisy GTK traceback in logs
    # when PyGObject isn't installed (the supported state on Linux now).
    # macOS uses Cocoa/WKWebView and Windows uses WebView2 (Edge Chromium);
    # `gui=None` lets pywebview pick the platform-native backend there.
    gui = "qt" if sys.platform.startswith("linux") else None
    # private_mode=False is harmless on Cocoa/WebView2/QtWebEngine and was
    # historically needed to keep localStorage alive on WebKit2GTK.
    webview.start(gui=gui, debug=dev_mode, private_mode=False)

    engine.shutdown()


if __name__ == "__main__":
    main()
