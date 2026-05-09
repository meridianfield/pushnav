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

import logging
import os
import signal
import sys
import threading
import urllib.error
import urllib.request

from evf.engine.engine import Engine

logger = logging.getLogger(__name__)

# Window dimensions sized to the React UI's `max-w-5xl` (1024px) layout
# plus minimal padding. Resizable, so the user can adjust on bigger screens.
# Each platform's webview (WKWebView / WebKit2GTK / WebView2) handles HiDPI
# scaling natively against its OS's DPI/scale settings — no app-side multiplier.
_VP_WIDTH = 1060
_VP_HEIGHT = 760


def _vite_running(port: int = 5173) -> bool:
    """True if **Vite's** dev server is reachable on localhost:`port`.

    A bare TCP probe isn't enough — common ports get squatted on by other
    services (e.g. macOS uses 5000 for AirPlay Receiver). We probe
    `/@vite/client` (a JS module Vite always serves) so unrelated
    listeners don't get mistaken for Vite.
    """
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/@vite/client", timeout=0.3
        ) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def main() -> None:
    # PUSHNAV_DEBUG=1 is equivalent to --dev (engine dev features +
    # WebKit inspector) on every platform.
    dev_mode = "--dev" in sys.argv or os.environ.get("PUSHNAV_DEBUG") == "1"
    no_window = "--no-window" in sys.argv
    # --react is now the default; accept the flag as a no-op for back-compat
    _ = "--react" in sys.argv

    engine = Engine(dev_mode=dev_mode)

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
    # prebuilt bundle through the in-process aiohttp server. This decouples
    # URL choice from dev_mode, so PUSHNAV_DEBUG=1 (or --dev) without Vite
    # still loads a working UI from :8765.
    target_url = (
        "http://localhost:5173" if _vite_running() else "http://localhost:8765"
    )
    title = f"PushNav {engine.app_version}"

    webview.create_window(
        title,
        target_url,
        width=_VP_WIDTH,
        height=_VP_HEIGHT,
        resizable=True,
    )
    # private_mode=False keeps HTML5 localStorage enabled in WebKit2GTK on
    # Linux (pywebview's GTK backend disables localStorage in private mode).
    # macOS WKWebView keeps localStorage alive regardless.
    webview.start(debug=dev_mode, private_mode=False)

    engine.shutdown()


if __name__ == "__main__":
    main()
