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
import sys

import dearpygui.dearpygui as dpg

from evf.engine.engine import Engine
from evf.ui.window import UI

logger = logging.getLogger(__name__)

_VP_WIDTH = 1280 // 2 + 320 + 35  # 995
_VP_HEIGHT = 720 // 2 + 60  # 420


def _windows_primary_monitor_dpi() -> int:
    """Return primary monitor's effective DPI on Windows, or 96 on failure.

    Uses GetScaleFactorForMonitor which returns the user-configured scale
    percentage (100, 125, 150, ...) even for DPI-unaware processes, unlike
    GetDpiForMonitor which virtualizes to 96 in that mode.
    """
    if sys.platform != "win32":
        return 96
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
            return 96
        return int(96 * scale.value / 100)
    except Exception:
        return 96


def main() -> None:
    dev_mode = "--dev" in sys.argv

    # Engine owns the ConfigManager — create it first so we can read hidpi
    engine = Engine()

    # First-launch auto-enable of 4K mode on Windows HiDPI displays. After
    # this runs once, the user's explicit checkbox choice always wins.
    if sys.platform == "win32" and not engine.config.hidpi_autodetected:
        if _windows_primary_monitor_dpi() >= 120 and not engine.config.hidpi:
            engine.config.hidpi = True
            logger.info("Auto-enabled 4K monitor compatibility mode (first launch)")
        engine.config.hidpi_autodetected = True

    vp_scale = 2 if engine.config.hidpi else 1

    # Create DPG context and full-size viewport
    dpg.create_context()
    dpg.configure_app(manual_callback_management=True)
    dpg.create_viewport(
        title=f"PushNav {engine.app_version} - Plate-Solving Push-To System",
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
    ui.set_telescope_activity_source(
        stellarium_active=lambda: engine.stellarium_has_client,
        lx200_active=lambda: engine.lx200_active,
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
