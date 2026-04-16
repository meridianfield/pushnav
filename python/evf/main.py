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

import platform
import sys

import dearpygui.dearpygui as dpg

from evf.engine.engine import Engine
from evf.ui.window import UI

_VP_WIDTH = 1280 // 2 + 320 + 35  # 995
_VP_HEIGHT = 720 // 2 + 60  # 420


def _get_windows_dpi_scale() -> float:
    """Declare DPI awareness and return the display scale factor on Windows.

    Must be called before any window/context creation.
    Returns 1.0 on non-Windows or on failure.
    """
    if platform.system() != "Windows":
        return 1.0
    try:
        import ctypes
        # PROCESS_PER_MONITOR_DPI_AWARE — tells Windows we handle DPI ourselves
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        dc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, dc)
        return dpi / 96.0
    except Exception:
        return 1.0


def main() -> None:
    dev_mode = "--dev" in sys.argv

    # Windows: declare DPI awareness *before* creating any window.
    # Returns the actual display scale (e.g. 1.5 for 150%).
    # On macOS / Linux this is always 1.0.
    win_dpi_scale = _get_windows_dpi_scale()

    # Engine owns the ConfigManager — create it first so we can read hidpi
    engine = Engine()

    # Determine viewport scale factor:
    # - Windows with active DPI scaling (125%+): use the real DPI scale
    # - Everything else (macOS, Linux, Windows at 100%): use hidpi toggle
    if platform.system() == "Windows" and win_dpi_scale > 1.0:
        vp_scale = win_dpi_scale
    else:
        vp_scale = 2 if engine.config.hidpi else 1

    # Create DPG context and full-size viewport
    dpg.create_context()
    dpg.configure_app(manual_callback_management=True)
    dpg.create_viewport(
        title="PushNav - Plate-Solving Push-To System",
        width=int(_VP_WIDTH * vp_scale),
        height=int(_VP_HEIGHT * vp_scale),
        resizable=False,
    )

    ui = UI(
        engine.frame_buffer,
        engine.pointing_state,
        engine.state_machine,
        engine.config,
        dev_mode=dev_mode,
        dpi_scale=win_dpi_scale,
    )
    ui.setup()

    dpg.setup_dearpygui()
    dpg.show_viewport()

    ui.update_splash("Initializing...")
    engine.startup_logging()

    ui.update_splash("Loading star database...")
    engine.startup_solver()

    ui.update_splash("Starting Stellarium server...")
    engine.startup_stellarium()

    ui.update_splash("Starting LX200 server...")
    engine.startup_lx200()

    ui.update_splash("Starting web server...")
    engine.startup_webserver()

    ui.update_splash("Connecting to camera...")
    engine.startup_camera()

    if not engine.camera_connected:
        ui.destroy_splash()
        should_exit = False

        def _set_exit():
            nonlocal should_exit
            should_exit = True

        ui.show_error_modal("Camera not found", on_close=_set_exit)

        while not should_exit:
            jobs = dpg.get_callback_queue()
            dpg.run_callbacks(jobs)
            dpg.render_dearpygui_frame()
        dpg.destroy_context()
        sys.exit(1)

    ui.update_splash("Preparing solver...")
    engine.startup_solver_thread()

    ui.set_on_step_advance(engine.step_advance)
    ui.set_on_set_control(engine.set_control)
    ui.set_failure_source(lambda: engine.consecutive_failures)
    ui.set_on_sync_retry(engine.sync_retry)
    ui.set_sync_select(engine.set_sync_selected)
    ui.set_sync_source(
        candidates=lambda: engine.sync_candidates,
        selected=lambda: engine.sync_selected_idx,
        in_progress=lambda: engine.sync_in_progress,
        error=lambda: engine.sync_error,
    )

    ui.set_on_use_prev_calibration(engine.use_previous_calibration)
    ui.set_on_audio_change(lambda v: setattr(engine, 'audio_enabled', v))
    if dev_mode:
        ui.set_on_inject_target(engine.goto_target.set)
    ui.set_navigation_source(
        goto_target=lambda: engine.goto_target.read(),
        on_clear=engine.clear_goto_target,
    )
    ui.set_stellarium_source(
        status=lambda: engine.stellarium_status,
        obj=lambda: engine.stellarium_object,
    )

    ui.destroy_splash()
    ui.set_audio_enabled(engine.audio_enabled)
    ui.set_web_url(engine.web_url)
    ui.set_lx200_address(
        engine.lx200_address if engine.lx200_running else "Server not running"
    )
    if engine.stellarium_address:
        ui.set_stellarium_address(engine.stellarium_address)
    else:
        ui.set_stellarium_address("Server not running")

    # Provide initial camera controls if connected
    controls = engine.camera_controls
    if controls:
        ui.update_controls(controls)

    ui.run()  # DearPyGui event loop — blocks until window close

    engine.shutdown()


if __name__ == "__main__":
    main()
