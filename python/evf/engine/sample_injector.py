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

"""Continuous sample-image injection for dev/debug.

When active, writes the same JPEG bytes into LatestFrame at 10 Hz, replacing
the camera's normal output. The solver picks it up like any other frame.
The camera client may also keep writing; whoever wins each tick is fine
because both are writing valid JPEGs at similar cadence.
"""

import io
import logging
import threading
import time
from pathlib import Path

from evf.engine.frame_buffer import LatestFrame

logger = logging.getLogger(__name__)


class SampleInjector:
    """Continuously injects a sample JPEG into the frame buffer."""

    _INTERVAL = 0.1  # 10 Hz

    def __init__(self, frame_buffer: LatestFrame) -> None:
        self._fb = frame_buffer
        self._jpeg: bytes | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._active_name: str | None = None  # for /ws payload

    @property
    def active_name(self) -> str | None:
        return self._active_name

    def set_jpeg(self, jpeg_bytes: bytes | None, name: str | None = None) -> None:
        """Start (or stop, if jpeg_bytes is None) continuous injection."""
        with self._lock:
            self._jpeg = jpeg_bytes
            self._active_name = name if jpeg_bytes is not None else None
            if jpeg_bytes is not None and (self._thread is None or not self._thread.is_alive()):
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._loop, name="sample-injector", daemon=True,
                )
                self._thread.start()

    def _loop(self) -> None:
        # Dynamically bump our frame_id above whatever's currently in the
        # buffer so we always win against the camera's stream. The camera at
        # 30 fps crosses any static offset in under an hour, which silently
        # broke injection in long-running engine sessions.
        while not self._stop.is_set():
            with self._lock:
                jpeg = self._jpeg
            if jpeg is None:
                # No sample selected — exit thread; another set() will restart.
                return
            _, _, current_id = self._fb.get()
            self._fb.set(jpeg, time.monotonic(), current_id + 1)
            self._stop.wait(self._INTERVAL)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def load_sample_jpeg(samples_dir: Path, name: str) -> bytes:
    """Load a PNG from samples_dir, encode as JPEG, return bytes."""
    from PIL import Image

    path = samples_dir / f"{name}.png"
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
