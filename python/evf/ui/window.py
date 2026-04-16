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

"""DearPyGui UI — live view, camera controls, tracking toggle, status display.

Per SPEC_ARCHITECTURE.md §4.1 and impl0.md §Phase 7.
Display-only layer that reads from shared data structures.
Engine wiring happens in Phase 8.
"""

import array
import io
import logging
import math
import time
from pathlib import Path
from typing import Callable

import dearpygui.dearpygui as dpg
import numpy as np
from PIL import Image

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTargetSnapshot
from evf.engine.navigation import (
    NavigationResult,
    compute_navigation,
    edge_arrow_position,
)
from evf.engine.pointing import PointingState
from evf.engine.state import EngineState, StateMachine
from evf.paths import fonts_dir, samples_dir, title_image

logger = logging.getLogger(__name__)

WIDTH = 1280
HEIGHT = 720
_CHANNELS = 4  # RGBA
_BASE_ZOOM = 0.5  # default zoom at 1x scale
_NO_STARS_THRESHOLD = 3  # consecutive failures before showing NO STARS
_LOCKED_THRESHOLD_DEG = 0.15  # 9 arcmin — "on target" / in eyepiece

_STATE_COLORS = {
    EngineState.SETUP: (200, 50, 50),
    EngineState.SYNC: (200, 50, 50),
    EngineState.SYNC_CONFIRM: (200, 50, 50),
    EngineState.CALIBRATE: (200, 50, 50),
    EngineState.WARMING_UP: (180, 40, 40),
    EngineState.TRACKING: (255, 70, 70),
    EngineState.RECONNECTING: (150, 35, 35),
    EngineState.ERROR: (255, 30, 30),
}


def _format_ra(ra_deg: float) -> str:
    """Convert RA in degrees to hours/minutes/seconds string."""
    ra_h = ra_deg / 15.0
    h = int(ra_h)
    m = int((ra_h - h) * 60)
    s = (ra_h - h - m / 60) * 3600
    return f"{h}h {m:02d}m {s:05.2f}s"


def _format_dec(dec_deg: float) -> str:
    """Convert Dec in degrees to degrees/arcmin/arcsec string."""
    sign = "+" if dec_deg >= 0 else "-"
    dec_abs = abs(dec_deg)
    d = int(dec_abs)
    m = int((dec_abs - d) * 60)
    s = (dec_abs - d - m / 60) * 3600
    return f"{sign}{d}\u00b0 {m:02d}' {s:04.1f}\""


class UI:
    """DearPyGui-based UI for the Electronic Viewfinder.

    Reads from shared data structures (LatestFrame, PointingState,
    StateMachine, ConfigManager) and renders the display.  Callbacks
    for tracking toggle and camera control changes are registered
    by the engine layer (Phase 8).
    """

    _SAMPLES_DIR = samples_dir()
    _SAMPLE_NAMES = ["a", "b", "c", "d", "orion"]
    _STEPS = [("1", "Camera"), ("2", "Sync"), ("3", "Roll"), ("4", "Track")]

    _STATE_TO_STEP = {
        EngineState.SETUP: "1",
        EngineState.SYNC: "2",
        EngineState.SYNC_CONFIRM: "2",
        EngineState.CALIBRATE: "3",
        EngineState.WARMING_UP: "4",
        EngineState.TRACKING: "4",
        EngineState.RECONNECTING: None,
        EngineState.ERROR: None,
    }
    _STATE_BUTTON_LABELS = {
        EngineState.SETUP: "Next",
        EngineState.SYNC: "Next",
        EngineState.SYNC_CONFIRM: "Confirm Sync",
        EngineState.CALIBRATE: "Skip",
        EngineState.WARMING_UP: "Stop tracking and restart setup",
        EngineState.TRACKING: "Stop tracking and restart setup",
    }
    _STEP_INSTRUCTIONS = {
        "1": (
            'To get good tracking performance, you should first complete the '
            'Setup step. This involves pointing the camera at the sky and making '
            'sure you can see stars in the preview. Make sure that the stars are '
            'reasonably well-focused and that the exposure is set to a level where '
            'stars are visible and tight. Press "Next" when you\'re ready to move '
            'on to the Sync step.'
        ),
        "2": (
            'This step involves syncing the camera\'s view with the telescope\'s '
            'pointing. Point the telescope at a bright star and make sure it is in '
            'the center of your eyepiece. Use higher power for best results. '
            'Remember: NOT in the center of the camera preview, but in the center '
            'of your eyepiece view. Then press "Next" to sync the tracker. '
            'If you have a saved calibration, press "Use Previous Calibration" '
            'to skip sync and start tracking immediately.'
        ),
        "2c": (
            'The highlighted star will be used for sync. If it\'s not the star you '
            'centered in your eyepiece, tap the correct star. Then press Confirm.'
        ),
        "3": (
            'Push the telescope UP (increase altitude) and hold steady until '
            'calibration completes automatically. This detects the finder camera '
            'rotation angle for accurate push-to directions. Press "Skip" to '
            'use the previously saved rotation angle.'
        ),
        "4": (
            'The plate-solving push-to system is now active. If you wish to '
            'restart the process, press the "Stop tracking and restart setup" button.'
        ),
    }

    def __init__(
        self,
        frame_buffer: LatestFrame,
        pointing_state: PointingState,
        state_machine: StateMachine,
        config: ConfigManager,
        *,
        dev_mode: bool = False,
        dpi_scale: float = 1.0,
    ) -> None:
        self._frame_buffer = frame_buffer
        self._pointing = pointing_state
        self._state_machine = state_machine
        self._config = config
        self._dev_mode = dev_mode
        self._dpi_scale = dpi_scale
        # Windows: use real DPI scale; macOS/Linux: use hidpi toggle (1x or 2x)
        if dpi_scale > 1.0:
            self._ui_scale = dpi_scale
        else:
            self._ui_scale = 2 if config.hidpi else 1
        self._texture_tag: int | str = 0
        self._last_rendered_frame_id = -1
        self._on_step_advance: Callable[[], None] | None = None
        self._on_set_control: Callable[[str, int], None] | None = None
        self._solver_failures: Callable[[], int] | None = None
        self._zoom = _BASE_ZOOM * self._ui_scale
        self._show_stars = False
        self._on_sync_retry: Callable[[], None] | None = None
        self._on_sync_select: Callable[[int], None] | None = None
        self._sync_candidates_getter: Callable[[], list | None] | None = None
        self._sync_selected_getter: Callable[[], int | None] | None = None
        self._sync_in_progress_getter: Callable[[], bool] | None = None
        self._sync_error_getter: Callable[[], str | None] | None = None
        self._on_audio_change: Callable[[bool], None] | None = None
        self._on_use_prev_calibration: Callable[[], None] | None = None
        self._goto_target_getter: Callable[[], GotoTargetSnapshot] | None = None
        self._on_clear_target: Callable[[], None] | None = None
        self._on_inject_target: Callable[[float, float], None] | None = None
        self._nav_result: NavigationResult | None = None
        self._stellarium_status_getter: Callable[[], dict | None] | None = None
        self._stellarium_object_getter: Callable[[], dict | None] | None = None
        self._debug_sample_jpeg: bytes | None = None  # cached JPEG for continuous injection
        self._debug_frame_id = 100_000  # offset to avoid collisions with real frames
        self._qr_texture: int | str | None = None

    # -- public API -----------------------------------------------------------

    def set_on_step_advance(self, callback: Callable[[], None]) -> None:
        """Register callback for wizard step advance."""
        self._on_step_advance = callback

    def set_on_set_control(self, callback: Callable[[str, int], None]) -> None:
        """Register callback for camera control changes. callback(id, value)."""
        self._on_set_control = callback

    def set_failure_source(self, getter: Callable[[], int]) -> None:
        """Set a callable that returns the current consecutive failure count."""
        self._solver_failures = getter

    def set_on_sync_retry(self, callback: Callable[[], None]) -> None:
        """Register callback for sync retry button."""
        self._on_sync_retry = callback

    def set_sync_select(self, callback: Callable[[int], None]) -> None:
        """Register callback for selecting a sync candidate."""
        self._on_sync_select = callback

    def set_on_audio_change(self, callback: Callable[[bool], None]) -> None:
        """Register callback for audio alert toggle. callback(enabled)."""
        self._on_audio_change = callback

    def set_on_use_prev_calibration(self, callback: Callable[[], None]) -> None:
        """Register callback for 'Use Previous Calibration' button."""
        self._on_use_prev_calibration = callback

    def set_on_inject_target(self, callback: Callable[[float, float], None]) -> None:
        """Register callback for debug target injection. callback(ra_deg, dec_deg)."""
        self._on_inject_target = callback

    def set_audio_enabled(self, value: bool) -> None:
        """Set the audio checkbox state (call after setup)."""
        if dpg.does_item_exist("audio_checkbox"):
            dpg.set_value("audio_checkbox", value)

    def set_sync_source(
        self,
        candidates: Callable[[], list | None],
        selected: Callable[[], int | None],
        in_progress: Callable[[], bool],
        error: Callable[[], str | None],
    ) -> None:
        """Set callables for sync state queries."""
        self._sync_candidates_getter = candidates
        self._sync_selected_getter = selected
        self._sync_in_progress_getter = in_progress
        self._sync_error_getter = error

    def set_navigation_source(
        self,
        goto_target: Callable[[], GotoTargetSnapshot],
        on_clear: Callable[[], None],
    ) -> None:
        """Set callables for navigation target queries."""
        self._goto_target_getter = goto_target
        self._on_clear_target = on_clear

    def set_stellarium_source(
        self,
        status: Callable[[], dict | None],
        obj: Callable[[], dict | None],
    ) -> None:
        """Set callables for Stellarium Remote Control data."""
        self._stellarium_status_getter = status
        self._stellarium_object_getter = obj

    def set_lx200_address(self, address: str) -> None:
        """Show LX200 TCP address in the settings panel.

        Format: "<ip>:<port>" (e.g. "192.168.1.42:4030").
        Users paste this into SkySafari / Stellarium Mobile / INDI / ASCOM.
        """
        if dpg.does_item_exist("lx200_address_label"):
            dpg.set_value("lx200_address_label", address)

    def set_stellarium_address(self, address: str) -> None:
        """Show desktop-Stellarium binary-protocol address in the settings panel.

        Format: "localhost:<port>" — desktop Stellarium's Telescope Control
        plugin only connects to the local machine (server binds 127.0.0.1).
        """
        if dpg.does_item_exist("stellarium_address_label"):
            dpg.set_value("stellarium_address_label", address)

    def set_web_url(self, url: str) -> None:
        """Show mobile web interface URL and QR code in the settings panel."""
        if dpg.does_item_exist("web_url_label"):
            dpg.set_value("web_url_label", url)
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color=(255, 70, 70), back_color=(10, 0, 0))
            qr_img = qr_img.convert("RGBA")
            qr_w, qr_h = qr_img.size
            import numpy as np
            qr_rgba = np.asarray(qr_img, dtype=np.float32).ravel() / 255.0
            with dpg.texture_registry():
                self._qr_texture = dpg.add_static_texture(
                    width=qr_w, height=qr_h, default_value=qr_rgba,
                )
            if dpg.does_item_exist("web_qr_group"):
                s = self._ui_scale
                dpg.add_image(
                    self._qr_texture,
                    width=int(qr_w * s), height=int(qr_h * s),
                    parent="web_qr_group",
                )
        except Exception as exc:
            logger.debug("QR code generation failed: %s", exc)

    def setup(self) -> None:
        """Build all DearPyGui widgets.

        Expects the DPG context and viewport to already exist.
        """
        # Font strategy — platform-specific for crisp rendering:
        #
        # Windows DPI-aware: rasterize at exact display size, no scaling.
        #   e.g. 150%: body=16*1.5=24px, global_font_scale=1.0 → no resampling
        # macOS Retina:  32px rasterized, *0.5=16px logical, 2x backing → crisp
        # Linux HiDPI:   32px rasterized, *1.0=32px in doubled viewport → crisp
        if self._dpi_scale > 1.0:
            # Windows: load at exact target size, scale=1.0 → zero artifacts
            base_body, base_heading, base_title = 16, 18, 28
            font_body_sz = int(base_body * self._dpi_scale)
            font_heading_sz = int(base_heading * self._dpi_scale)
            font_title_sz = int(base_title * self._dpi_scale)
            dpg.set_global_font_scale(1.0)
        else:
            # macOS / Linux: original 2x-rasterize + scale-down approach
            font_body_sz, font_heading_sz, font_title_sz = 32, 36, 56
            hidpi_scale = 2 if self._config.hidpi else 1
            dpg.set_global_font_scale(0.5 * hidpi_scale)
        _fonts = fonts_dir()
        font_path = str(_fonts / "Inter-Regular.ttf")
        font_bold_path = str(_fonts / "Inter-Bold.ttf")
        with dpg.font_registry():
            self._font_body = dpg.add_font(font_path, font_body_sz)
            self._font_heading = dpg.add_font(font_bold_path, font_heading_sz)
            self._font_title = dpg.add_font(font_bold_path, font_title_sz)
        dpg.bind_font(self._font_body)

        # Full red night-vision theme (preserves dark adaptation)
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                # Text
                dpg.add_theme_color(dpg.mvThemeCol_Text, (200, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (100, 30, 30))
                # Backgrounds
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (25, 5, 5))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (25, 5, 5))
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (30, 8, 8))
                # Borders (hidden globally; video frame uses its own theme)
                dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, (0, 0, 0, 0))
                # Frame (slider tracks, input backgrounds)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (40, 8, 8))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (60, 12, 12))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (70, 15, 15))
                # Title bar
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (20, 4, 4))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (40, 8, 8))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed, (15, 2, 2))
                # Scrollbar
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (15, 2, 2))
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (80, 15, 15))
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, (120, 25, 25))
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, (150, 35, 35))
                # Slider grab / checkmark
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (150, 35, 35))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (200, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (200, 50, 50))
                # Button
                dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 10, 10))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 18, 18))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (110, 25, 25))
                # Separator
                dpg.add_theme_color(dpg.mvThemeCol_Separator, (80, 15, 15))
                dpg.add_theme_color(dpg.mvThemeCol_SeparatorHovered, (120, 25, 25))
                dpg.add_theme_color(dpg.mvThemeCol_SeparatorActive, (150, 35, 35))
                # Header (collapsible, selectable)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (40, 8, 8))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (60, 12, 12))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (80, 18, 18))
                # Tab
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (30, 6, 6))
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (60, 12, 12))
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (50, 10, 10))
                # Resize grip
                dpg.add_theme_color(dpg.mvThemeCol_ResizeGrip, (50, 10, 10))
                dpg.add_theme_color(dpg.mvThemeCol_ResizeGripHovered, (80, 18, 18))
                dpg.add_theme_color(dpg.mvThemeCol_ResizeGripActive, (110, 25, 25))
                # Rounded corners for a polished look
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 3)
        dpg.bind_theme(global_theme)

        # Tight vertical spacing for title block
        with dpg.theme() as self._title_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 0)
                dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 0, 0)

        # Pill badge themes for step indicators (disabled buttons)
        with dpg.theme() as self._pill_inactive_theme:
            with dpg.theme_component(dpg.mvButton, enabled_state=False):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 2)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
                dpg.add_theme_color(dpg.mvThemeCol_Button, (40, 8, 8))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (100, 30, 30))
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (100, 30, 30))
        with dpg.theme() as self._pill_active_theme:
            with dpg.theme_component(dpg.mvButton, enabled_state=False):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 2)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
                dpg.add_theme_color(dpg.mvThemeCol_Button, (150, 30, 30))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (255, 50, 50))

        # Video container border theme
        with dpg.theme() as self._video_border_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Border, (80, 15, 15))

        # Create blank RGBA texture using array.array for proper buffer interface
        initial_data = array.array("f", [0.0] * (WIDTH * HEIGHT * _CHANNELS))
        with dpg.texture_registry():
            self._texture_tag = dpg.add_raw_texture(
                width=WIDTH,
                height=HEIGHT,
                default_value=initial_data,
                format=dpg.mvFormat_Float_rgba,
            )

        # Load title image for sidebar branding
        title_img_path = title_image()
        title_img = Image.open(title_img_path).convert("RGBA")
        self._title_img_w, self._title_img_h = title_img.size
        title_rgba = np.asarray(title_img, dtype=np.float32).ravel() / 255.0
        with dpg.texture_registry():
            self._title_texture = dpg.add_static_texture(
                width=self._title_img_w,
                height=self._title_img_h,
                default_value=title_rgba,
            )

        self._build_layout()
        self._build_splash_overlay()

    def update_splash(self, message: str) -> None:
        """Update splash status text and render one frame."""
        if dpg.does_item_exist("splash_status"):
            dpg.set_value("splash_status", message)
        dpg.render_dearpygui_frame()

    def destroy_splash(self) -> None:
        """Remove splash overlay and enable side panel."""
        if dpg.does_item_exist("splash_window"):
            dpg.delete_item("splash_window")
        self._set_side_panel_enabled(True)

    def show_error_modal(self, message: str, on_close: Callable[[], None]) -> None:
        """Show a modal error dialog with an OK button."""
        s = self._ui_scale
        vp_w = dpg.get_viewport_width()
        vp_h = dpg.get_viewport_height()
        modal_w, modal_h = 400 * s, 150 * s
        btn_w = 80 * s
        with dpg.window(
            tag="error_modal",
            modal=True,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True,
            pos=[(vp_w - modal_w) // 2, (vp_h - modal_h) // 2],
            width=modal_w,
            height=modal_h,
        ):
            dpg.add_spacer(height=20)
            dpg.add_text(message, indent=(modal_w - len(message) * 7) // 2)
            dpg.add_spacer(height=15)
            dpg.add_button(
                label="OK",
                width=btn_w,
                indent=(modal_w - btn_w) // 2,
                callback=lambda: (
                    dpg.delete_item("error_modal"),
                    on_close(),
                ),
            )

        with dpg.theme() as modal_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (132, 22, 22))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (200, 60, 60))
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 2)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
        dpg.bind_item_theme("error_modal", modal_theme)

    def _show_restart_notice(self) -> None:
        """Show a modal telling the user to restart for the change to take effect."""
        if dpg.does_item_exist("restart_modal"):
            return
        s = self._ui_scale
        vp_w = dpg.get_viewport_width()
        vp_h = dpg.get_viewport_height()
        modal_w, modal_h = 400 * s, 130 * s
        btn_w = 80 * s
        msg = "Restart required for this change to take effect."
        with dpg.window(
            tag="restart_modal",
            modal=True,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True,
            pos=[(vp_w - modal_w) // 2, (vp_h - modal_h) // 2],
            width=modal_w,
            height=modal_h,
        ):
            dpg.add_spacer(height=20)
            dpg.add_text(msg, wrap=modal_w - 40, indent=20)
            dpg.add_spacer(height=15)
            dpg.add_button(
                label="OK",
                width=btn_w,
                indent=(modal_w - btn_w) // 2,
                callback=lambda: dpg.delete_item("restart_modal"),
            )
        with dpg.theme() as modal_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (132, 22, 22))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (200, 60, 60))
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 2)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
        dpg.bind_item_theme("restart_modal", modal_theme)

    def run(self) -> None:
        """Run the DearPyGui render loop. Blocks until window is closed."""
        while dpg.is_dearpygui_running():
            try:
                self._update()
            except Exception:
                logger.exception("_update() failed")
            jobs = dpg.get_callback_queue()
            dpg.run_callbacks(jobs)
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def update_controls(self, controls: list[dict]) -> None:
        """Rebuild camera control sliders from CONTROL_INFO data."""
        if dpg.does_item_exist("controls_group"):
            dpg.delete_item("controls_group", children_only=True)
        for ctrl in controls:
            ctrl_id = ctrl["id"]
            label = ctrl.get("label", ctrl_id)
            dpg.add_slider_int(
                label=label,
                tag=f"ctrl_{ctrl_id}",
                default_value=ctrl.get("cur", ctrl.get("min", 0)),
                min_value=ctrl.get("min", 0),
                max_value=ctrl.get("max", 100),
                callback=self._on_control_change,
                user_data=ctrl_id,
                parent="controls_group",
                width=230 * self._ui_scale,
            )

    # -- layout ---------------------------------------------------------------

    def _build_layout(self) -> None:
        s = self._ui_scale
        with dpg.window(tag="primary_window"):
            with dpg.group(horizontal=True):
                # Left: scrollable video container with border
                _video_w = int(WIDTH * _BASE_ZOOM * self._ui_scale) + 18
                with dpg.child_window(tag="video_container", border=True,
                                      horizontal_scrollbar=True,
                                      width=_video_w):
                    dpg.add_image(
                        self._texture_tag,
                        tag="live_image",
                        width=int(WIDTH * self._zoom),
                        height=int(HEIGHT * self._zoom),
                    )
                    with dpg.item_handler_registry() as handler:
                        dpg.add_item_clicked_handler(
                            callback=self._on_preview_click
                        )
                    dpg.bind_item_handler_registry("live_image", handler)
                dpg.bind_item_theme("video_container", self._video_border_theme)

                # Right: fixed-width side panel
                with dpg.child_window(width=320 * s, tag="side_panel", no_scrollbar=False):
                    self._build_title_section()
                    dpg.add_separator()
                    dpg.add_spacer(height=5)
                    self._build_state_section()
                    dpg.add_separator()
                    self._build_navigation_section()
                    dpg.add_separator()
                    self._build_controls_section()
                    dpg.add_separator()
                    self._build_settings_section()
                    dpg.add_separator()
                    self._build_advanced_settings_section()
                    dpg.add_separator()
                    self._build_status_section()
                    if self._dev_mode:
                        dpg.add_separator()
                        self._build_debug_section()

        dpg.set_primary_window("primary_window", True)

    def _build_title_section(self) -> None:
        s = self._ui_scale
        dpg.add_image(
            self._title_texture,
            width=self._title_img_w * s // 2,
            height=self._title_img_h * s // 2,
        )
        dpg.add_spacer(height=6)

    def _build_steps_section(self) -> None:
        s = self._ui_scale
        with dpg.group(horizontal=True):
            for num, label in self._STEPS:
                dpg.add_button(
                    label=num, tag=f"pill_{num}", width=24 * s, height=24 * s, enabled=False
                )
                dpg.bind_item_theme(f"pill_{num}", self._pill_inactive_theme)
                dpg.add_text(label, tag=f"pill_label_{num}")

    def _build_state_section(self) -> None:
        s = self._ui_scale
        self._build_steps_section()
        dpg.add_spacer(height=5)
        dpg.add_text(
            self._STEP_INSTRUCTIONS["1"],
            tag="step_instructions",
            wrap=300 * s,
            color=(200, 50, 50),
        )
        dpg.add_spacer(height=5)
        dpg.add_text("", tag="sync_status_label", wrap=300 * s, color=(255, 100, 100))
        dpg.configure_item("sync_status_label", show=False)
        dpg.add_button(
            label="Next",
            tag="tracking_btn",
            callback=self._on_step_advance_click,
            width=-1,
        )
        dpg.add_button(
            label="Retry",
            tag="sync_retry_btn",
            callback=self._on_sync_retry_click,
            width=-1,
        )
        dpg.configure_item("sync_retry_btn", show=False)
        dpg.add_button(
            label="Use Previous Calibration",
            tag="prev_cal_btn",
            callback=self._on_use_prev_calibration_click,
            width=-1,
        )
        dpg.configure_item("prev_cal_btn", show=False)
        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_text("Status: SETUP", tag="state_label", color=(200, 50, 50))
        dpg.bind_item_font("state_label", self._font_heading)
        dpg.add_text("", tag="state_radec_label", color=(200, 50, 50))
        dpg.configure_item("state_radec_label", show=False)

    def _build_controls_section(self) -> None:
        s = self._ui_scale
        heading = dpg.add_text("Camera Controls", color=(255, 70, 70))
        dpg.bind_item_font(heading, self._font_heading)
        dpg.add_slider_float(
            label="Zoom",
            tag="zoom_slider",
            default_value=self._zoom * 100,
            min_value=25.0 * s,
            max_value=200.0 * s,
            format="%.0f%%",
            width=230 * s,
            callback=self._on_zoom_change,
        )
        with dpg.group(tag="controls_group"):
            dpg.add_text(
                "(waiting for camera...)",
                tag="controls_placeholder",
                color=(150, 150, 150),
            )

    def _build_status_section(self) -> None:
        heading = dpg.add_text("Plate-Solve Stats", color=(255, 70, 70))
        dpg.bind_item_font(heading, self._font_heading)
        dpg.add_text("RA:  --", tag="ra_label")
        dpg.add_text("Dec: --", tag="dec_label")
        dpg.add_text("Roll: --", tag="roll_label")
        dpg.add_spacer(height=3)
        dpg.add_text("Matches: --", tag="matches_label")
        dpg.add_text("Prob: --", tag="prob_label")
        dpg.add_text("Last solve: --", tag="solve_age_label")
        dpg.add_text("Failures: 0", tag="failures_label")

    def _build_navigation_section(self) -> None:
        dpg.add_text("TARGET: --", tag="nav_target_label")
        dpg.add_text("", tag="nav_target_coords", color=(150, 40, 40))
        dpg.add_text("", tag="nav_detail_label", color=(200, 50, 50))

        dpg.add_text(
            "1\u00b0 ~ 2 full moons wide",
            tag="nav_scale_label",
            color=(100, 30, 30),
        )
        dpg.configure_item("nav_scale_label", show=False)
        dpg.add_button(
            label="Clear Target",
            tag="nav_clear_btn",
            callback=self._on_clear_target_click,
            width=-1,
        )
        dpg.configure_item("nav_clear_btn", show=False)

    def _build_settings_section(self) -> None:
        heading = dpg.add_text("Settings", color=(255, 70, 70))
        dpg.bind_item_font(heading, self._font_heading)
        dpg.add_checkbox(
            label="Show detected stars",
            tag="show_stars_checkbox",
            default_value=False,
            callback=self._on_show_stars_change,
        )
        dpg.add_checkbox(
            label="Audio alerts",
            tag="audio_checkbox",
            default_value=self._config.audio_enabled,
            callback=self._on_audio_change_click,
        )
        # On Windows, DPI scaling is handled automatically — no checkbox needed.
        if self._dpi_scale <= 1.0:
            dpg.add_checkbox(
                label="4K monitor compatibility mode",
                tag="hidpi_checkbox",
                default_value=self._config.hidpi,
                callback=self._on_hidpi_change,
            )
        dpg.add_spacer(height=6)
        dpg.add_separator()
        mobile_heading = dpg.add_text("Mobile Interface", color=(255, 70, 70))
        dpg.bind_item_font(mobile_heading, self._font_heading)
        dpg.add_text("Starting...", tag="web_url_label", color=(200, 50, 50))
        dpg.add_group(tag="web_qr_group")
        dpg.add_spacer(height=6)
        dpg.add_separator()
        telescope_heading = dpg.add_text("Telescope Control", color=(255, 70, 70))
        dpg.bind_item_font(telescope_heading, self._font_heading)
        dpg.add_text(
            "LX200 (SkySafari / Stellarium Mobile / INDI / ASCOM):",
            color=(180, 180, 180),
        )
        dpg.add_text("Starting...", tag="lx200_address_label", color=(200, 50, 50))
        dpg.add_spacer(height=4)
        dpg.add_text("Stellarium (desktop, same machine only):", color=(180, 180, 180))
        dpg.add_text(
            "Starting...", tag="stellarium_address_label", color=(200, 50, 50)
        )

    def _build_advanced_settings_section(self) -> None:
        s = self._ui_scale
        heading = dpg.add_text("Advanced Settings", color=(255, 70, 70))
        dpg.bind_item_font(heading, self._font_heading)
        dpg.add_input_int(
            label="Min matches",
            tag="min_matches_input",
            default_value=self._config.min_matches,
            min_value=1,
            min_clamped=True,
            step=1,
            width=120 * s,
            callback=self._on_min_matches_change,
        )
        dpg.add_input_float(
            label="Max prob",
            tag="max_prob_input",
            default_value=self._config.max_prob,
            min_value=0.0001,
            max_value=1.0,
            min_clamped=True,
            max_clamped=True,
            format="%.4f",
            step=0.01,
            width=120 * s,
            callback=self._on_max_prob_change,
        )

    def _build_debug_section(self) -> None:
        heading = dpg.add_text("Debug", color=(255, 70, 70))
        dpg.bind_item_font(heading, self._font_heading)
        dpg.add_button(
            label="Capture Frame",
            tag="debug_capture_btn",
            callback=self._on_capture_frame,
            width=-1,
        )
        dpg.add_text("", tag="debug_capture_status", color=(150, 40, 40))
        dpg.add_spacer(height=5)
        dpg.add_button(
            label="Inject Capella",
            tag="debug_inject_capella_btn",
            callback=self._on_inject_capella,
            width=-1,
        )
        dpg.add_spacer(height=5)
        dpg.add_text("Inject sample image as video input:")
        for name in self._SAMPLE_NAMES:
            dpg.add_checkbox(
                label=f"Sample {name}.png",
                tag=f"debug_sample_{name}",
                default_value=False,
                callback=self._on_debug_sample_change,
                user_data=name,
            )

    def _set_side_panel_enabled(self, enabled: bool) -> None:
        """Enable or disable all interactive widgets in the side panel."""
        def _walk(item: int) -> None:
            try:
                dpg.configure_item(item, enabled=enabled)
            except SystemError:
                pass
            for slot in range(3):
                for child in (dpg.get_item_children(item, slot=slot) or []):
                    _walk(child)
        if dpg.does_item_exist("side_panel"):
            _walk(dpg.get_alias_id("side_panel"))

    def _build_splash_overlay(self) -> None:
        """Build splash status text at bottom-left of the viewport."""
        s = self._ui_scale
        self._set_side_panel_enabled(False)
        with dpg.window(
            tag="splash_window",
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True,
            no_background=True,
            pos=(10, int(HEIGHT * _BASE_ZOOM * self._ui_scale) + 10),
            width=400 * s,
            height=40 * s,
        ):
            dpg.add_text(
                "Starting...", tag="splash_status", color=(200, 50, 50)
            )

    # -- per-frame update (main thread only) ----------------------------------

    def _update(self) -> None:
        if self._debug_sample_jpeg is not None:
            self._debug_frame_id += 1
            self._frame_buffer.set(
                self._debug_sample_jpeg, time.monotonic(), self._debug_frame_id
            )
        self._update_texture()
        # Snapshot state and failures once to avoid TOCTOU race between
        # _update_state and _update_status reading different values.
        state = self._state_machine.state
        failures = self._solver_failures() if self._solver_failures else 0
        self._update_state(state, failures)
        self._update_status(state, failures)
        self._update_navigation()

    def _update_texture(self) -> None:
        jpeg_bytes, _ts, frame_id = self._frame_buffer.get()
        if jpeg_bytes is None or frame_id == self._last_rendered_frame_id:
            return
        self._last_rendered_frame_id = frame_id
        try:
            img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGBA")
            img = img.resize((WIDTH, HEIGHT))
            if self._show_stars:
                self._draw_star_overlay(img)
            if self._state_machine.state == EngineState.SYNC_CONFIRM:
                self._draw_sync_candidates(img)
            self._draw_coordinate_axes(img)
            self._draw_navigation_overlay(img)
            self._draw_location_overlay(img)
            rgba = np.asarray(img, dtype=np.float32).ravel() / 255.0
            dpg.set_value(self._texture_tag, rgba)
        except Exception as exc:
            logger.debug("Frame decode error: %s", exc)

    def _update_state(self, state: EngineState, failures: int) -> None:
        no_stars = (
            state in (EngineState.CALIBRATE, EngineState.WARMING_UP, EngineState.TRACKING)
            and failures >= _NO_STARS_THRESHOLD
        )
        color = _STATE_COLORS.get(state, (200, 50, 50))
        if no_stars:
            dpg.set_value("state_label", f"Status: {state.value}: NO STARS")
        else:
            dpg.set_value("state_label", f"Status: {state.value}")

        # Breathing color pulse for active states
        if state == EngineState.TRACKING and not no_stars:
            t = time.monotonic()
            pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 1.5))
            color = tuple(int(c * pulse) for c in color)
        elif no_stars:
            t = time.monotonic()
            pulse = 0.5 + 0.5 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 0.7))
            color = tuple(int(c * pulse) for c in color)

        dpg.configure_item("state_label", color=color)

        # Update step pills, button label, and instructional text
        step = self._STATE_TO_STEP.get(state)
        if step is not None:
            for num, _label in self._STEPS:
                if num == step:
                    dpg.bind_item_theme(f"pill_{num}", self._pill_active_theme)
                    dpg.configure_item(f"pill_label_{num}", color=(255, 50, 50))
                else:
                    dpg.bind_item_theme(f"pill_{num}", self._pill_inactive_theme)
                    dpg.configure_item(f"pill_label_{num}", color=(100, 30, 30))
            btn_label = self._STATE_BUTTON_LABELS.get(state, "Next")
            dpg.configure_item("tracking_btn", label=btn_label)
            instr_key = "2c" if state == EngineState.SYNC_CONFIRM else step
            dpg.set_value("step_instructions", self._STEP_INSTRUCTIONS[instr_key])

        # Camera controls enabled in SETUP and SYNC only
        controls_enabled = state in (EngineState.SETUP, EngineState.SYNC)
        for tag in self._control_tags():
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, enabled=controls_enabled)

        # Star overlay only meaningful when solver has run
        solving = state in (
            EngineState.SYNC_CONFIRM, EngineState.CALIBRATE,
            EngineState.WARMING_UP, EngineState.TRACKING,
        )
        dpg.configure_item("show_stars_checkbox", enabled=solving)
        if not solving:
            self._show_stars = False
            dpg.set_value("show_stars_checkbox", False)

        # Tracking button disabled during ERROR/RECONNECTING or while sync solving
        sync_solving = (
            self._sync_in_progress_getter() if self._sync_in_progress_getter else False
        )
        btn_enabled = state not in (EngineState.ERROR, EngineState.RECONNECTING)
        if state == EngineState.SYNC and sync_solving:
            btn_enabled = False
        dpg.configure_item("tracking_btn", enabled=btn_enabled)

        # Sync status label
        sync_error = (
            self._sync_error_getter() if self._sync_error_getter else None
        )
        if state == EngineState.SYNC and sync_solving:
            dpg.set_value("sync_status_label", "Solving...")
            dpg.configure_item("sync_status_label", show=True)
        elif state == EngineState.SYNC and sync_error:
            dpg.set_value("sync_status_label", sync_error)
            dpg.configure_item("sync_status_label", show=True)
        else:
            dpg.configure_item("sync_status_label", show=False)

        # Retry button only in SYNC_CONFIRM
        dpg.configure_item(
            "sync_retry_btn", show=(state == EngineState.SYNC_CONFIRM)
        )

        # "Use Previous Calibration" button in SYNC state when config has saved data
        dpg.configure_item(
            "prev_cal_btn",
            show=(state == EngineState.SYNC and self._config.has_calibration),
        )

    def _update_status(self, state: EngineState, failures: int) -> None:
        snap = self._pointing.read()
        no_stars = (
            state in (EngineState.CALIBRATE, EngineState.WARMING_UP, EngineState.TRACKING)
            and failures >= _NO_STARS_THRESHOLD
        )

        # RA/Dec summary line below the status label (state section)
        show_radec = (
            state in (EngineState.CALIBRATE, EngineState.WARMING_UP, EngineState.TRACKING)
            and snap.valid
            and not no_stars
        )
        if show_radec:
            radec = f"{_format_ra(snap.ra_j2000)}  {_format_dec(snap.dec_j2000)}"
            dpg.set_value("state_radec_label", radec)
            dpg.configure_item("state_radec_label", show=True)
        else:
            dpg.configure_item("state_radec_label", show=False)

        if no_stars:
            dpg.set_value("ra_label", f"RA:  {_format_ra(0.0)}")
            dpg.set_value("dec_label", f"Dec: {_format_dec(90.0)}")
            dpg.set_value("roll_label", "Roll: --")
            dpg.set_value("matches_label", "Matches: 0")
            dpg.set_value("prob_label", "Prob: --")
            dpg.set_value("solve_age_label", "Last solve: --")
        elif snap.valid:
            dpg.set_value("ra_label", f"RA:  {_format_ra(snap.ra_j2000)}")
            dpg.set_value("dec_label", f"Dec: {_format_dec(snap.dec_j2000)}")
            dpg.set_value("roll_label", f"Roll: {snap.roll:.1f}\u00b0")
            dpg.set_value("matches_label", f"Matches: {snap.matches}")
            dpg.set_value("prob_label", f"Prob: {snap.prob:.6f}")
            age = time.monotonic() - snap.last_success_timestamp
            dpg.set_value("solve_age_label", f"Last solve: {age:.1f}s ago")
        elif state == EngineState.WARMING_UP:
            dpg.set_value("ra_label", "RA:  solving...")
            dpg.set_value("dec_label", "Dec: solving...")
            dpg.set_value("roll_label", "Roll: --")
            dpg.set_value("matches_label", "Matches: --")
            dpg.set_value("prob_label", "Prob: --")
            dpg.set_value("solve_age_label", "Last solve: --")

        dpg.set_value("failures_label", f"Failures: {failures}")

    def _control_tags(self) -> list[str]:
        """Return tags of all camera control slider widgets."""
        tags = []
        if dpg.does_item_exist("controls_group"):
            children = dpg.get_item_children("controls_group", slot=1) or []
            for child in children:
                alias = dpg.get_item_alias(child)
                if alias and alias.startswith("ctrl_"):
                    tags.append(alias)
        return tags

    # -- navigation -----------------------------------------------------------

    _FOV_H = 8.86  # horizontal FOV in degrees (matches solver config)

    def _update_navigation(self) -> None:
        """Update navigation sidebar labels and compute nav result for overlay."""
        if not self._goto_target_getter:
            return
        target = self._goto_target_getter()
        if not target.active:
            self._nav_result = None
            dpg.set_value("nav_target_label", "TARGET: --")
            dpg.set_value("nav_target_coords", "")
            dpg.set_value("nav_detail_label", "")
            dpg.configure_item("nav_scale_label", show=False)
            dpg.configure_item("nav_clear_btn", show=False)
            return

        ra_str = _format_ra(target.ra_j2000)
        dec_str = _format_dec(target.dec_j2000)
        # Show object name if available from Stellarium
        obj_name = None
        if self._stellarium_object_getter:
            obj = self._stellarium_object_getter()
            if obj:
                obj_name = obj.get("localized-name") or obj.get("name")
        if obj_name:
            dpg.set_value("nav_target_label", f"TARGET: {obj_name}")
        else:
            dpg.set_value("nav_target_label", "TARGET:")
        dpg.set_value("nav_target_coords", f"{ra_str}  {dec_str}")
        dpg.configure_item("nav_clear_btn", show=True)

        snap = self._pointing.read()
        if not snap.valid:
            dpg.set_value("nav_detail_label", "Dist: --")
            dpg.configure_item("nav_scale_label", show=False)
            self._nav_result = None
            return

        nav = compute_navigation(
            snap.ra_j2000,
            snap.dec_j2000,
            snap.roll,
            target.ra_j2000,
            target.dec_j2000,
            self._FOV_H,
            WIDTH,
            HEIGHT,
        )
        self._nav_result = nav

        # Rotate camera-relative deltas to mount frame using finder_rotation.
        # finder_rotation = CW angle from image-up to mount-up in the image.
        # Mount basis in image coords: mount_up = (sin(phi), cos(phi)),
        # mount_right = (cos(phi), -sin(phi)).  To project image-frame
        # components (delta_right, delta_up) onto mount basis:
        phi = math.radians(self._config.finder_rotation)
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        mount_right = nav.delta_right_deg * cos_phi - nav.delta_up_deg * sin_phi
        mount_up = nav.delta_right_deg * sin_phi + nav.delta_up_deg * cos_phi

        # Format distance and direction components
        if nav.separation_deg >= 1.0:
            sep_s = f"{nav.separation_deg:.1f}\u00b0"
            lr_v = abs(mount_right)
            ud_v = abs(mount_up)
            lr_s = f"{'Right' if mount_right >= 0 else 'Left'} {lr_v:.1f}\u00b0"
            ud_s = f"{'Up' if mount_up >= 0 else 'Down'} {ud_v:.1f}\u00b0"
        else:
            sep_s = f"{nav.separation_deg * 60:.1f}'"
            lr_v = abs(mount_right * 60)
            ud_v = abs(mount_up * 60)
            lr_s = f"{'Right' if mount_right >= 0 else 'Left'} {lr_v:.1f}'"
            ud_s = f"{'Up' if mount_up >= 0 else 'Down'} {ud_v:.1f}'"

        dpg.set_value("nav_detail_label", f"Dist: {sep_s} | {lr_s} | {ud_s}")
        dpg.configure_item("nav_scale_label", show=True)

    def _sync_offset_pixel(self) -> tuple[float, float]:
        """Pixel position of the sync offset (where main scope points).

        Falls back to image center when no sync is available.
        """
        cx, cy = WIDTH / 2.0, HEIGHT / 2.0
        d_body = self._config.sync_d_body
        if d_body is not None and d_body[2] > 0.1:
            scale = WIDTH / (2.0 * math.tan(math.radians(self._FOV_H / 2.0)))
            cx += (-d_body[0] / d_body[2]) * scale
            cy += (-d_body[1] / d_body[2]) * scale
        return cx, cy

    def _draw_coordinate_axes(self, img: Image.Image) -> None:
        """Draw coordinate cross rotated by finder_rotation.

        finder_rotation is the angle (degrees) from image-up to mount-up,
        measured clockwise in the image. When finder_rotation=0, mount-up
        equals image-up (camera mounted perfectly upright).
        """
        state = self._state_machine.state
        if state not in (
            EngineState.CALIBRATE, EngineState.WARMING_UP, EngineState.TRACKING,
        ):
            return
        snap = self._pointing.read()
        if not snap.valid:
            return
        # Hide axes during NO STARS, same as star markers
        failures = self._solver_failures() if self._solver_failures else 0
        if failures >= _NO_STARS_THRESHOLD:
            return

        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)
        color = (255, 70, 70, 200)

        # Load overlay font (cached after first call)
        if not hasattr(self, "_overlay_font"):
            self._overlay_font = ImageFont.truetype(
                str(fonts_dir() / "Inter-Bold.ttf"), 24
            )
        font = self._overlay_font

        cx, cy = self._sync_offset_pixel()

        # Rotation by finder_rotation: mount-up direction in screen coords
        phi = math.radians(self._config.finder_rotation)
        up_dx, up_dy = math.sin(phi), -math.cos(phi)      # mount-up in screen
        right_dx, right_dy = math.cos(phi), math.sin(phi)  # mount-right in screen

        # Draw dashed cross lines through center, extending to image edges
        half_diag = math.sqrt(WIDTH * WIDTH + HEIGHT * HEIGHT) / 2.0
        dash_on, dash_off = 12, 8
        dash_step = dash_on + dash_off
        for dx, dy in [(up_dx, up_dy), (right_dx, right_dy)]:
            total = int(half_diag * 2)
            t = 0
            while t < total:
                seg_end = min(t + dash_on, total)
                frac_s = t / total
                frac_e = seg_end / total
                x0 = cx + dx * (frac_s * 2 - 1) * half_diag
                y0 = cy + dy * (frac_s * 2 - 1) * half_diag
                x1 = cx + dx * (frac_e * 2 - 1) * half_diag
                y1 = cy + dy * (frac_e * 2 - 1) * half_diag
                draw.line([(x0, y0), (x1, y1)], fill=color, width=1)
                t += dash_step

        # Draw labels 100px from center, rotated along axis
        label_color = (255, 70, 70, 220)
        label_dist = 200

        # PIL CCW rotation angles for text along each axis
        up_axis_rot = 90 - self._config.finder_rotation    # for RIGHT/LEFT
        right_axis_rot = -self._config.finder_rotation      # for UP/DOWN

        # UP/DOWN sit on mount-right axis, RIGHT/LEFT sit on mount-up axis
        labels = [
            ("UP",    cx - right_dx * label_dist, cy - right_dy * label_dist, right_axis_rot),
            ("DOWN",  cx + right_dx * label_dist, cy + right_dy * label_dist, right_axis_rot),
            ("RIGHT", cx + up_dx * label_dist,    cy + up_dy * label_dist,    up_axis_rot),
            ("LEFT",  cx - up_dx * label_dist,    cy - up_dy * label_dist,    up_axis_rot),
        ]
        for text, lx, ly, rot in labels:
            self._draw_rotated_text(img, text, lx, ly, rot, font, label_color)

    def _draw_navigation_overlay(self, img: Image.Image) -> None:
        """Draw push-to navigation overlay with proximity-coded zones.

        Three zones based on target proximity:
        - PUSH: target off-screen — dim reticle, guide line to edge arrow
        - CONVERGE: target in FOV — brighter reticle, guide line to target
        - LOCKED: on target (< 0.15 deg) — pulsing concentric rings
        """
        nav = self._nav_result
        if nav is None:
            return
        # Hide navigation overlay during NO STARS, same as star markers/axes
        failures = self._solver_failures() if self._solver_failures else 0
        if failures >= _NO_STARS_THRESHOLD:
            return

        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)
        t = time.monotonic()

        # Ensure overlay font is loaded
        if not hasattr(self, "_overlay_font"):
            self._overlay_font = ImageFont.truetype(
                str(fonts_dir() / "Inter-Bold.ttf"), 24
            )

        # Sync offset — where main scope points in the camera image
        ox, oy = self._sync_offset_pixel()
        dx_off = ox - WIDTH / 2.0
        dy_off = oy - HEIGHT / 2.0

        # Get target name from Stellarium object info
        target_name = None
        if self._stellarium_object_getter:
            obj = self._stellarium_object_getter()
            if obj:
                target_name = obj.get("localized-name") or obj.get("name")

        # Determine zone
        if nav.in_fov and nav.separation_deg <= _LOCKED_THRESHOLD_DEG:
            zone = "LOCKED"
        elif nav.in_fov:
            zone = "CONVERGE"
        else:
            zone = "PUSH"

        if zone == "PUSH":
            # Compute edge arrow position
            if nav.pixel_x is not None and nav.pixel_y is not None:
                ex, ey, angle = edge_arrow_position(
                    nav.pixel_x + dx_off, nav.pixel_y + dy_off, WIDTH, HEIGHT,
                    origin_x=ox, origin_y=oy,
                )
            else:
                # Target behind camera — derive direction from camera_angle
                angle = nav.camera_angle_deg
                far = max(WIDTH, HEIGHT) * 10.0
                rad = math.radians(angle)
                far_x = ox + far * math.sin(rad)
                far_y = oy - far * math.cos(rad)
                ex, ey, angle = edge_arrow_position(
                    far_x, far_y, WIDTH, HEIGHT,
                    origin_x=ox, origin_y=oy,
                )

            self._draw_nav_reticle(draw, ox, oy, zone, t)
            # Guide line from reticle to edge (arrow draws on top)
            self._draw_nav_guide_line(draw, ox, oy, ex, ey, zone)
            # Arrow tip 68px inward from edge, pointing toward reticle
            rad = math.radians(angle)
            tip_x = ex - math.sin(rad) * 68
            tip_y = ey + math.cos(rad) * 68
            self._draw_arrow_with_tail(draw, tip_x, tip_y, (angle + 180) % 360)
            self._draw_nav_distance(
                draw, nav.separation_deg, zone, ex, ey, arrow_angle_deg=angle,
            )

        elif zone == "CONVERGE":
            tx = nav.pixel_x + dx_off
            ty = nav.pixel_y + dy_off
            self._draw_nav_reticle(draw, ox, oy, zone, t)
            self._draw_nav_guide_line(draw, ox, oy, tx, ty, zone)
            self._draw_nav_target_marker(draw, tx, ty)
            self._draw_nav_distance(draw, nav.separation_deg, zone, tx, ty)
            if target_name:
                self._draw_target_name(img, draw, target_name, tx + 18, ty - 12)

        else:  # LOCKED
            self._draw_nav_reticle(draw, ox, oy, zone, t)
            font = self._overlay_font
            pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 1.2))
            alpha = int(255 * pulse)
            color = (255, 120, 80, alpha)
            pad = 5
            # Target name above reticle
            if target_name:
                bbox = font.getbbox(target_name)
                tw = bbox[2] - bbox[0]
                tx = ox - tw / 2
                ty = oy - 45
                self._composite_rounded_rect(
                    img,
                    tx + bbox[0] - pad, ty + bbox[1] - pad,
                    tx + bbox[2] + pad, ty + bbox[3] + pad,
                )
                draw.text((tx, ty), target_name, fill=color, font=font)
            # "ON TARGET" text below reticle
            text = "ON TARGET"
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            tx = ox - tw / 2
            ty = oy + 35
            self._composite_rounded_rect(
                img,
                tx + bbox[0] - pad, ty + bbox[1] - pad,
                tx + bbox[2] + pad, ty + bbox[3] + pad,
            )
            draw.text((tx, ty), text, fill=color, font=font)

    def _draw_nav_reticle(
        self, draw, ox: float, oy: float, zone: str, t: float,
    ) -> None:
        """Draw proximity-coded reticle at the sync offset position."""
        if zone == "PUSH":
            color = (120, 25, 25, 160)
            r, arm, gap, w = 12, 20, 4, 1
        elif zone == "CONVERGE":
            color = (200, 50, 50, 200)
            r, arm, gap, w = 14, 24, 5, 2
        else:  # LOCKED — pulsing concentric rings
            pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 1.2))
            alpha = int(255 * pulse)
            color = (255, 120, 80, alpha)
            for ring_r in (20, 14, 8):
                ring_w = 3 if ring_r == 14 else 2
                draw.ellipse(
                    [ox - ring_r, oy - ring_r, ox + ring_r, oy + ring_r],
                    outline=color, width=ring_w,
                )
            dot_r = 4
            draw.ellipse(
                [ox - dot_r, oy - dot_r, ox + dot_r, oy + dot_r], fill=color,
            )
            return

        # Ring + cross arms (PUSH and CONVERGE)
        draw.ellipse([ox - r, oy - r, ox + r, oy + r], outline=color, width=w)
        draw.line([(ox - arm, oy), (ox - gap, oy)], fill=color, width=w)
        draw.line([(ox + gap, oy), (ox + arm, oy)], fill=color, width=w)
        draw.line([(ox, oy - arm), (ox, oy - gap)], fill=color, width=w)
        draw.line([(ox, oy + gap), (ox, oy + arm)], fill=color, width=w)

        # Lock zone ring in CONVERGE — shows the 0.15 deg threshold radius
        if zone == "CONVERGE":
            scale = WIDTH / (2.0 * math.tan(math.radians(self._FOV_H / 2.0)))
            lock_r = math.tan(math.radians(_LOCKED_THRESHOLD_DEG)) * scale
            draw.ellipse(
                [ox - lock_r, oy - lock_r, ox + lock_r, oy + lock_r],
                outline=(200, 50, 50, 60), width=1,
            )

    @staticmethod
    def _draw_nav_guide_line(
        draw, x1: float, y1: float, x2: float, y2: float, zone: str,
    ) -> None:
        """Draw guide line from reticle to target/arrow."""
        if zone == "PUSH":
            color = (255, 100, 50, 230)
            w = 2
        else:
            color = (255, 70, 70, 200)
            w = 1
        draw.line([(x1, y1), (x2, y2)], fill=color, width=w)

    @staticmethod
    def _draw_nav_target_marker(draw, tx: float, ty: float) -> None:
        """Draw small crosshair at projected target position (CONVERGE zone)."""
        color = (255, 70, 70, 200)
        r, gap, arm = 8, 3, 14
        draw.ellipse([tx - r, ty - r, tx + r, ty + r], outline=color, width=1)
        draw.line([(tx - arm, ty), (tx - gap, ty)], fill=color, width=1)
        draw.line([(tx + gap, ty), (tx + arm, ty)], fill=color, width=1)
        draw.line([(tx, ty - arm), (tx, ty - gap)], fill=color, width=1)
        draw.line([(tx, ty + gap), (tx, ty + arm)], fill=color, width=1)

    @staticmethod
    def _composite_rounded_rect(
        img: Image.Image, x0: float, y0: float, x1: float, y1: float,
        radius: int = 4, fill: tuple = (40, 5, 5, 140),
    ) -> None:
        """Alpha-composite a semitransparent rounded rectangle onto img."""
        from PIL import Image as PILImage, ImageDraw as PILImageDraw

        overlay = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
        od = PILImageDraw.Draw(overlay)
        od.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)
        img.alpha_composite(overlay)

    def _draw_target_name(
        self, img: Image.Image, draw, name: str, x: float, y: float,
    ) -> None:
        """Draw target object name label with dark background at the given position."""
        font = self._overlay_font
        bbox = font.getbbox(name)
        # bbox = (left, top, right, bottom) — top is the glyph top bearing
        pad_x, pad_y = 5, 5
        self._composite_rounded_rect(
            img,
            x + bbox[0] - pad_x, y + bbox[1] - pad_y,
            x + bbox[2] + pad_x, y + bbox[3] + pad_y,
        )
        draw.text((x, y), name, fill=(255, 70, 70, 200), font=font)

    def _draw_location_overlay(self, img: Image.Image) -> None:
        """Draw observer location in the top-left corner."""
        if not self._stellarium_status_getter:
            return
        status = self._stellarium_status_getter()
        if not status:
            return
        loc = status.get("location", {})
        city = loc.get("name", "")
        country = loc.get("country", "")
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if not city and lat is None:
            return

        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)
        if not hasattr(self, "_overlay_font"):
            self._overlay_font = ImageFont.truetype(
                str(fonts_dir() / "Inter-Bold.ttf"), 24
            )
        font = self._overlay_font
        color = (255, 70, 70, 160)

        if city and country:
            line1 = f"{city}, {country}"
        elif city:
            line1 = city
        else:
            line1 = ""

        if lat is not None and lon is not None:
            line2 = f"{lat:.4f}\u00b0, {lon:.4f}\u00b0"
        else:
            line2 = ""

        # Measure text to draw background box
        pad = 5
        lines = [l for l in [line1, line2] if l]
        if not lines:
            return
        max_w = max(font.getbbox(l)[2] - font.getbbox(l)[0] for l in lines)
        line_h = 26
        box_h = len(lines) * line_h + pad * 2
        self._composite_rounded_rect(
            img, 4, 4, 8 + max_w + pad * 2, 4 + box_h,
        )
        y = 4 + pad
        for line in lines:
            draw.text((8 + pad, y), line, fill=color, font=font)
            y += line_h

    def _draw_nav_distance(
        self, draw, sep_deg: float, zone: str,
        x: float, y: float, arrow_angle_deg: float | None = None,
    ) -> None:
        """Render separation distance text on the overlay."""
        font = self._overlay_font
        if sep_deg >= 1.0:
            text = f"{sep_deg:.1f}\u00b0"
        else:
            text = f"{sep_deg * 60:.1f}'"

        if zone == "PUSH":
            color = (255, 100, 50, 230)
            # Position near arrow, offset back along direction and to the side
            if arrow_angle_deg is not None:
                rad = math.radians(arrow_angle_deg)
                lx = x - math.sin(rad) * 70 + math.cos(rad) * 15
                ly = y + math.cos(rad) * 70 + math.sin(rad) * 15
            else:
                lx, ly = x + 15, y
        else:  # CONVERGE
            color = (255, 70, 70, 200)
            lx, ly = x + 18, y - 12

        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        lx = max(4, min(WIDTH - tw - 4, lx))
        ly = max(4, min(HEIGHT - th - 4, ly))
        draw.text((lx, ly), text, fill=color, font=font)

    @staticmethod
    def _draw_rotated_text(img, text, cx, cy, angle_deg, font, color):
        """Draw text centered at (cx, cy), rotated by angle_deg (PIL CCW)."""
        from PIL import ImageDraw as _ID

        # Normalize to (-90, 90] so text is never upside-down
        a = angle_deg % 360
        if 90 < a <= 270:
            a -= 180

        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad = 4
        temp = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        _ID.Draw(temp).text(
            (pad - bbox[0], pad - bbox[1]), text, fill=color, font=font,
        )
        rotated = temp.rotate(a, expand=True, resample=Image.BICUBIC)
        rw, rh = rotated.size
        img.paste(rotated, (int(cx - rw / 2), int(cy - rh / 2)), rotated)

    @staticmethod
    def _draw_arrow_with_tail(
        draw, x: float, y: float, angle_deg: float,
        size: int = 28, tail_len: int = 40,
    ) -> None:
        """Draw a bright arrow with tail at (x,y) pointing toward angle_deg.

        angle_deg: clockwise from image-up (0=up, 90=right, 180=down, 270=left).
        The tip is at (x,y); the tail extends behind the arrowhead toward center.
        """
        color = (255, 100, 50, 255)

        rad = math.radians(angle_deg)
        # Direction unit vector (in screen coords: +x right, +y down)
        dx = math.sin(rad)
        dy = -math.cos(rad)
        # Perpendicular unit vector
        px = -dy
        py = dx

        # Arrowhead triangle
        half_base = size * 0.4
        bx1 = x - size * dx + half_base * px
        by1 = y - size * dy + half_base * py
        bx2 = x - size * dx - half_base * px
        by2 = y - size * dy - half_base * py
        draw.polygon(
            [(x, y), (bx1, by1), (bx2, by2)],
            fill=color,
            outline=color,
        )

        # Tail line from arrowhead base center backward
        base_cx = x - size * dx
        base_cy = y - size * dy
        tail_x = base_cx - tail_len * dx
        tail_y = base_cy - tail_len * dy
        draw.line(
            [(base_cx, base_cy), (tail_x, tail_y)],
            fill=color, width=3,
        )

    # -- callbacks ------------------------------------------------------------

    def _on_step_advance_click(self, sender, app_data, user_data) -> None:
        logger.info("Next clicked, has_callback=%s", self._on_step_advance is not None)
        try:
            if self._on_step_advance:
                self._on_step_advance()
        except Exception:
            logger.exception("step_advance callback failed")

    def _on_control_change(self, sender, app_data, user_data) -> None:
        control_id = user_data
        value = app_data
        if self._on_set_control:
            self._on_set_control(control_id, value)

    def _on_min_matches_change(self, sender, app_data, user_data) -> None:
        self._config.min_matches = app_data

    def _on_max_prob_change(self, sender, app_data, user_data) -> None:
        self._config.max_prob = app_data

    def _on_show_stars_change(self, sender, app_data, user_data) -> None:
        self._show_stars = app_data

    def _on_audio_change_click(self, sender, app_data, user_data) -> None:
        if self._on_audio_change:
            self._on_audio_change(app_data)

    def _on_hidpi_change(self, sender, app_data, user_data) -> None:
        self._config.hidpi = app_data
        self._show_restart_notice()

    def _on_clear_target_click(self, sender, app_data, user_data) -> None:
        if self._on_clear_target:
            self._on_clear_target()

    def _on_sync_retry_click(self, sender, app_data, user_data) -> None:
        if self._on_sync_retry:
            self._on_sync_retry()

    def _on_use_prev_calibration_click(self, sender, app_data, user_data) -> None:
        if self._on_use_prev_calibration:
            self._on_use_prev_calibration()

    def _on_preview_click(self, sender, app_data) -> None:
        """Handle click on preview image to select a sync candidate."""
        if self._state_machine.state != EngineState.SYNC_CONFIRM:
            return
        candidates = (
            self._sync_candidates_getter() if self._sync_candidates_getter else None
        )
        if not candidates:
            return
        # Get mouse position in viewport coordinates
        mouse_pos = dpg.get_mouse_pos(local=False)
        # Get the image item's screen-space position
        img_pos = dpg.get_item_rect_min("live_image")
        # Click position relative to the image widget
        rel_x = mouse_pos[0] - img_pos[0]
        rel_y = mouse_pos[1] - img_pos[1]
        # Current display size of the image
        disp_w = int(WIDTH * self._zoom)
        disp_h = int(HEIGHT * self._zoom)
        if not (0 <= rel_x <= disp_w and 0 <= rel_y <= disp_h):
            return
        # Scale to original image coords via the display texture (WIDTH x HEIGHT)
        # Candidates are in original image coords; we need image_size to scale
        # Get image_size from first candidate's source
        # We use the texture dimensions (WIDTH x HEIGHT) as intermediate
        # The candidate overlay scales by HEIGHT/image_h and WIDTH/image_w
        # So we need to reverse: pixel_in_original = pixel_in_display / zoom / scale
        # pixel_in_texture = rel / zoom, then reverse the scale
        tex_x = rel_x / self._zoom
        tex_y = rel_y / self._zoom
        # Find nearest candidate — candidates are in original image coords
        # We need image_size to compute scale factors; get from pointing snapshot
        snap = self._pointing.read()
        if snap.image_size:
            img_h, img_w = snap.image_size
        else:
            # Fallback: assume texture size == image size
            img_h, img_w = HEIGHT, WIDTH
        sx = WIDTH / img_w
        sy = HEIGHT / img_h
        # Convert texture-space click to original image coords
        click_img_x = tex_x / sx
        click_img_y = tex_y / sy
        # Find nearest candidate
        best_idx = -1
        best_dist_sq = float("inf")
        threshold = max(img_w, img_h) * 0.05  # 5% of image dimension
        threshold_sq = threshold * threshold
        for i, c in enumerate(candidates):
            dx = c.x - click_img_x
            dy = c.y - click_img_y
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist_sq and dist_sq < threshold_sq:
                best_dist_sq = dist_sq
                best_idx = i
        if best_idx >= 0 and self._on_sync_select:
            self._on_sync_select(best_idx)

    def _on_debug_sample_change(self, sender, app_data, user_data) -> None:
        name = user_data
        if app_data:
            # Turning on — uncheck other samples (radio-button behavior)
            for other in self._SAMPLE_NAMES:
                if other != name:
                    dpg.set_value(f"debug_sample_{other}", False)
            self._load_debug_sample(name)
        else:
            self._debug_sample_jpeg = None
            # Reset frame buffer so camera frames (lower IDs) are accepted again
            self._frame_buffer.clear()

    def _load_debug_sample(self, name: str) -> None:
        """Load a sample PNG, encode as JPEG, and cache for continuous injection."""
        if self._SAMPLES_DIR is None:
            logger.warning("Sample images not available in bundled mode")
            return
        path = self._SAMPLES_DIR / f"{name}.png"
        try:
            img = Image.open(path)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            self._debug_sample_jpeg = buf.getvalue()
            logger.info("Debug sample loaded: %s", path.name)
        except Exception as exc:
            logger.error("Failed to load sample %s: %s", name, exc)

    def _on_inject_capella(self, sender, app_data, user_data) -> None:
        """Inject Capella as a GOTO target (debug only)."""
        # Capella J2000: RA 79.1723°, Dec +45.9980°
        if self._on_inject_target:
            self._on_inject_target(79.1723, 45.9980)
            logger.info("Debug: injected Capella as GOTO target")

    def _on_capture_frame(self, sender, app_data, user_data) -> None:
        """Save the current raw camera frame as PNG to ~/Downloads."""
        jpeg_bytes, _ts, _fid = self._frame_buffer.get()
        if jpeg_bytes is None:
            dpg.set_value("debug_capture_status", "No frame available")
            return
        try:
            img = Image.open(io.BytesIO(jpeg_bytes))
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest = Path.home() / "Downloads" / f"evf_capture_{timestamp}.png"
            img.save(dest, format="PNG")
            dpg.set_value("debug_capture_status", f"Saved: {dest.name}")
            logger.info("Frame captured: %s", dest)
        except Exception as exc:
            dpg.set_value("debug_capture_status", f"Error: {exc}")
            logger.error("Capture failed: %s", exc)

    def _on_zoom_change(self, sender, app_data, user_data) -> None:
        self._zoom = app_data / 100.0
        dpg.configure_item(
            "live_image",
            width=int(WIDTH * self._zoom),
            height=int(HEIGHT * self._zoom),
        )

    # -- star overlay ---------------------------------------------------------

    def _draw_star_overlay(self, img: Image.Image) -> None:
        """Draw detected and matched star circles on the frame."""
        snapshot = self._pointing.read()
        if not snapshot.valid or snapshot.all_centroids is None:
            return

        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)

        # Scale from original image coords to display size
        sy = HEIGHT / snapshot.image_size[0]
        sx = WIDTH / snapshot.image_size[1]

        # All detected: dim red, small circles
        for cy, cx in snapshot.all_centroids:
            x, y = cx * sx, cy * sy
            r = 4
            draw.ellipse([x - r, y - r, x + r, y + r],
                         outline=(150, 40, 40, 180), width=1)

        # Matched: bright red, larger circles
        if snapshot.matched_centroids:
            for cy, cx in snapshot.matched_centroids:
                x, y = cx * sx, cy * sy
                r = 6
                draw.ellipse([x - r, y - r, x + r, y + r],
                             outline=(255, 70, 70, 220), width=2)

    def _draw_sync_candidates(self, img: Image.Image) -> None:
        """Draw sync candidate markers on the frame (SYNC_CONFIRM state)."""
        candidates = (
            self._sync_candidates_getter() if self._sync_candidates_getter else None
        )
        selected_idx = (
            self._sync_selected_getter() if self._sync_selected_getter else None
        )
        if not candidates:
            return

        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)

        # Determine scale from original image to display texture
        snap = self._pointing.read()
        if snap.image_size:
            img_h, img_w = snap.image_size
        else:
            img_h, img_w = HEIGHT, WIDTH
        sy = HEIGHT / img_h
        sx = WIDTH / img_w

        for i, c in enumerate(candidates):
            x, y = c.x * sx, c.y * sy
            if i == selected_idx:
                # Selected: bright red, larger
                r = 12
                draw.ellipse([x - r, y - r, x + r, y + r],
                             outline=(255, 70, 70, 255), width=3)
                # Inner dot
                r2 = 3
                draw.ellipse([x - r2, y - r2, x + r2, y + r2],
                             fill=(255, 70, 70, 255))
            else:
                # Unselected: dim red
                r = 8
                draw.ellipse([x - r, y - r, x + r, y + r],
                             outline=(150, 40, 40, 180), width=2)
