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
import signal
import sys
import threading

from evf.engine.engine import Engine

logger = logging.getLogger(__name__)

# Window dimensions sized to the React UI's `max-w-5xl` (1024px) layout
# plus minimal padding. Resizable, so the user can adjust on bigger screens.
_VP_WIDTH = 1060
_VP_HEIGHT = 760
_CHROME_BUFFER = 0  # legacy DPG nudge — pywebview's content area already
                    # excludes window chrome, no extra padding needed


def _windows_primary_monitor_scale() -> int:
    """Return primary monitor's scale percentage (100, 125, 150, ...).

    Uses GetScaleFactorForMonitor, which returns the user-configured scale
    even for DPI-unaware processes (unlike GetDpiForMonitor, which
    virtualizes to 96 in that mode). Returns 100 on non-Windows or on
    failure.
    """
    if sys.platform != "win32":
        return 100
    try:
        import ctypes
        from ctypes import wintypes

        MONITOR_DEFAULTTOPRIMARY = 1
        hmon = ctypes.windll.user32.MonitorFromPoint(
            wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY
        )
        scale = ctypes.c_int(100)
        if ctypes.windll.shcore.GetScaleFactorForMonitor(
            hmon, ctypes.byref(scale)
        ) != 0:
            return 100
        return int(scale.value)
    except Exception:
        return 100


def main() -> None:
    dev_mode = "--dev" in sys.argv
    no_window = "--no-window" in sys.argv
    # --react is now the default; accept the flag as a no-op for back-compat
    _ = "--react" in sys.argv

    engine = Engine(dev_mode=dev_mode)

    # Auto-toggle 4K mode on Windows whenever the detected display scale
    # changes (different monitor, docking, Windows scaling changed). Within a
    # single scale, the user's checkbox choice is preserved.
    if sys.platform == "win32":
        current_scale = _windows_primary_monitor_scale()
        if current_scale != engine.config.hidpi_last_scale:
            should_hidpi = current_scale >= 150
            if engine.config.hidpi != should_hidpi:
                engine.config.hidpi = should_hidpi
                logger.info(
                    "Auto-%s 4K mode for %d%% display scale",
                    "enabled" if should_hidpi else "disabled",
                    current_scale,
                )
            engine.config.hidpi_last_scale = current_scale

    vp_scale = 2 if engine.config.hidpi else 1

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

    target_url = "http://localhost:5000" if dev_mode else "http://localhost:8080"
    title = f"PushNav {engine.app_version}"

    webview.create_window(
        title,
        target_url,
        width=int(_VP_WIDTH * vp_scale) + _CHROME_BUFFER,
        height=int(_VP_HEIGHT * vp_scale),
        resizable=True,
    )
    webview.start()  # blocks until window closed

    engine.shutdown()


if __name__ == "__main__":
    main()
