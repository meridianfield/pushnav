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

"""Audio alerts for star lock/lost transitions during tracking."""

import logging
import threading
from pathlib import Path

from evf.paths import sounds_dir

logger = logging.getLogger(__name__)

_SOUNDS_DIR = sounds_dir()
_LOCK_SOUND = _SOUNDS_DIR / "lock.wav"
_LOST_SOUND = _SOUNDS_DIR / "lost.wav"

# Defer playsound3 import — gracefully degrade if not installed
_available = False
_playsound = None
try:
    from playsound3 import playsound as _playsound

    _available = True
except ImportError:
    logger.warning("playsound3 not installed — audio alerts disabled")


class AudioAlert:
    """Plays a sound on failure-count transitions.

    Transitions detected:
      0 → >0  →  play lost sound  (stars lost)
      >0 → 0  →  play lock sound  (stars re-acquired)

    Thread-safe: call from any thread. Sound plays non-blocking.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self._lock = threading.Lock()
        self._enabled = enabled
        self._prev_failures = 0

    def on_failure_count_changed(self, new_count: int) -> None:
        """Notify of a new consecutive-failure count. Plays sound on transition."""
        with self._lock:
            prev = self._prev_failures
            self._prev_failures = new_count
            if not self._enabled:
                return
            should_play_lost = prev == 0 and new_count > 0
            should_play_lock = prev > 0 and new_count == 0

        if should_play_lost:
            self._play(_LOST_SOUND)
        elif should_play_lock:
            self._play(_LOCK_SOUND)

    def reset(self) -> None:
        """Reset state — call when solver starts or stops."""
        with self._lock:
            self._prev_failures = 0

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        with self._lock:
            self._enabled = value

    @staticmethod
    def _play(path: Path) -> None:
        """Play a sound file. Never raises — logs errors instead."""
        if not _available or _playsound is None:
            return
        try:
            _playsound(str(path), block=False)
        except Exception as exc:
            logger.debug("Audio playback failed (%s): %s", path.name, exc)
