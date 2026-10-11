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

"""Engine status on the Raspberry Pi's built-in LEDs (headless only).

A headless Pi has no screen, so the green ACT and red PWR LEDs show
whether PushNav needs attention (red) or is making progress (green).
The LEDs must already be writable: the pushnav-headless service's root
helper (evf.engine.led_helper) sets trigger=none and grants write
access before PushNav starts, and restores them when it stops.

Blinking is driven from this thread, not the kernel `timer` trigger, so
a crashed process can't leave a blinking "all good" behind.
"""

import logging
import math
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from evf.engine.state import EngineState

logger = logging.getLogger(__name__)

LEDS_SYSFS = Path("/sys/class/leds")
# Current kernels name them ACT / PWR; older ones led0 / led1.
_LED_NAMES = {"green": ("ACT", "led0"), "red": ("PWR", "led1")}

# Same threshold SolverThread uses for the "lost" sound.
LOST_AFTER_FAILURES = 3


@dataclass(frozen=True)
class Pattern:
    """One LED driven by a repeating sequence of (brightness, seconds) steps."""

    led: str  # "green" or "red"
    steps: tuple[tuple[int, float], ...]


def _blink(led: str, on_s: float, off_s: float) -> Pattern:
    return Pattern(led, ((1, on_s), (0, off_s)))


RED_STEADY = Pattern("red", ((1, math.inf),))
GREEN_STEADY = Pattern("green", ((1, math.inf),))
RED_SLOW_BLINK = _blink("red", 0.5, 1.5)
GREEN_DOUBLE_BLINK = Pattern("green", ((1, 0.15), (0, 0.15), (1, 0.15), (0, 1.55)))
GREEN_SLOW_BLINK = _blink("green", 0.5, 1.5)
GREEN_FAST_BLINK = _blink("green", 0.1, 0.1)
GREEN_BLIP = _blink("green", 0.06, 2.94)
# Shown once, over the status pattern, when a client connects or sends a
# target; the trailing gap keeps it apart from the pattern that resumes.
ACTIVITY_FLASH = Pattern(
    "green", ((1, 0.05), (0, 0.05), (1, 0.05), (0, 0.05), (1, 0.05), (0, 0.15))
)


def pattern_for(
    state: EngineState, camera_connected: bool, failures: int, has_red: bool
) -> Pattern:
    """Map engine status to an LED pattern; the first matching rule wins.

    Without a red LED (Pi Zero 2 W), the red patterns fall back to green
    patterns that don't clash with the green ones.
    """
    if state == EngineState.ERROR:
        return RED_STEADY if has_red else GREEN_STEADY
    if not camera_connected or state == EngineState.RECONNECTING:
        return RED_SLOW_BLINK if has_red else GREEN_DOUBLE_BLINK
    if state == EngineState.TRACKING:
        return GREEN_FAST_BLINK if failures >= LOST_AFTER_FAILURES else GREEN_BLIP
    return GREEN_SLOW_BLINK


def find_leds(root: Path = LEDS_SYSFS) -> dict[str, Path]:
    """Writable LED brightness files by colour, e.g. {"green": .../ACT/brightness}.

    Only LEDs this process may write are returned, so a source/dev run
    without the root helper gets an empty dict and leaves the LEDs alone.
    """
    found: dict[str, Path] = {}
    for colour, names in _LED_NAMES.items():
        for name in names:
            path = root / name / "brightness"
            if path.exists() and os.access(path, os.W_OK):
                found[colour] = path
                break
    return found


class StatusLedController:
    """Daemon thread that keeps the LEDs in step with the engine status.

    `snapshot` returns (state, camera_connected, consecutive_failures) and
    is polled every `poll_s`. Brightness is written only when it changes.
    A failed write disables the controller rather than retrying forever.
    `flash()` shows ACTIVITY_FLASH once, then the status pattern resumes.
    """

    def __init__(
        self,
        snapshot: Callable[[], tuple[EngineState, bool, int]],
        leds: dict[str, Path],
        poll_s: float = 0.1,
    ) -> None:
        self._snapshot = snapshot
        self._leds = leds
        self._poll_s = poll_s
        self._written: dict[str, int] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pattern: Pattern | None = None
        self._flash_requested = threading.Event()
        self._flashing = False
        # What is on the LEDs now (the status pattern or ACTIVITY_FLASH).
        self._shown: Pattern | None = None
        self._step = 0
        self._step_end = 0.0

    @property
    def pattern(self) -> Pattern | None:
        """The status pattern (for logs and tests); a flash doesn't change it."""
        return self._pattern

    def flash(self) -> None:
        """Ask for one ACTIVITY_FLASH. Safe from any thread, never blocks.

        Requests that arrive while a flash is showing are merged into it.
        """
        self._flash_requested.set()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="status-led", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        for colour in self._leds:
            self._write(colour, 0)

    # -- internal -------------------------------------------------------------

    def _current_pattern(self) -> Pattern | None:
        try:
            state, connected, failures = self._snapshot()
        except Exception as exc:  # engine mid-shutdown etc. — keep the last one
            logger.debug("Status LED snapshot failed: %s", exc)
            return self._pattern
        return pattern_for(state, connected, failures, has_red="red" in self._leds)

    def _show(self, pattern: Pattern, step: int) -> bool:
        value = pattern.steps[step][0]
        for colour in self._leds:
            if not self._write(colour, value if colour == pattern.led else 0):
                return False
        return True

    def _write(self, colour: str, value: int) -> bool:
        if self._written.get(colour) == value:
            return True
        try:
            self._leds[colour].write_text(str(value))
        except OSError as exc:
            logger.warning("Status LED disabled: cannot write %s (%s)",
                           self._leds[colour], exc)
            self._stop.set()
            return False
        self._written[colour] = value
        return True

    def _start_pattern(self, pattern: Pattern, now: float) -> bool:
        self._shown, self._step = pattern, 0
        self._step_end = now + pattern.steps[0][1]
        return self._show(pattern, 0)

    def _poll(self, now: float) -> bool:
        pattern = self._current_pattern()
        if pattern is not None and pattern != self._pattern:
            logger.debug("Status LED: %s", pattern)
            self._pattern = pattern
            if not self._flashing and not self._start_pattern(pattern, now):
                return False
        if self._flash_requested.is_set() and not self._flashing:
            self._flash_requested.clear()
            self._flashing = True
            return self._start_pattern(ACTIVITY_FLASH, now)
        return True

    def _advance(self, now: float) -> bool:
        pattern = self._shown
        assert pattern is not None
        self._step += 1
        if self._flashing and self._step == len(pattern.steps):
            # One flash only: drop requests that came in during it, then
            # resume the status pattern from its first step.
            self._flashing = False
            self._flash_requested.clear()
            if self._pattern is None:
                self._shown = None
                return True
            return self._start_pattern(self._pattern, now)
        self._step %= len(pattern.steps)
        # Advance from the scheduled end so blinks don't drift; resync if
        # we fell a whole step behind (e.g. a stall).
        self._step_end += pattern.steps[self._step][1]
        if self._step_end < now:
            self._step_end = now + pattern.steps[self._step][1]
        return self._show(pattern, self._step)

    def _run(self) -> None:
        self._step_end = next_poll = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_poll:
                next_poll = now + self._poll_s
                if not self._poll(now):
                    return
            if self._shown is not None and now >= self._step_end:
                if not self._advance(now):
                    return
            self._stop.wait(max(0.0, min(next_poll, self._step_end) - time.monotonic()))
