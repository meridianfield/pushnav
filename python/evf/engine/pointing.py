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

"""Thread-safe container for the last valid plate-solve result."""

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PointingSnapshot:
    """Immutable snapshot of pointing state, safe to pass between threads."""

    ra_j2000: float
    dec_j2000: float
    roll: float
    matches: int
    prob: float
    last_success_timestamp: float
    valid: bool
    all_centroids: list | None = None       # List of [y, x] for all detected stars
    matched_centroids: list | None = None   # List of [y, x] for matched stars
    image_size: tuple[int, int] | None = None  # (height, width)


class PointingState:
    """Thread-safe pointing state. Updated only by the solver thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ra_j2000: float = 0.0
        self._dec_j2000: float = 0.0
        self._roll: float = 0.0
        self._matches: int = 0
        self._prob: float = 0.0
        self._last_success_timestamp: float = 0.0
        self._valid: bool = False
        self._all_centroids: list | None = None
        self._matched_centroids: list | None = None
        self._image_size: tuple[int, int] | None = None

    def update(
        self,
        ra_j2000: float,
        dec_j2000: float,
        roll: float,
        matches: int,
        prob: float,
        *,
        all_centroids: list | None = None,
        matched_centroids: list | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> None:
        """Update with a new valid solve result. Called only by solver thread."""
        with self._lock:
            self._ra_j2000 = ra_j2000
            self._dec_j2000 = dec_j2000
            self._roll = roll
            self._matches = matches
            self._prob = prob
            self._last_success_timestamp = time.monotonic()
            self._valid = True
            self._all_centroids = all_centroids
            self._matched_centroids = matched_centroids
            self._image_size = image_size

    def read(self) -> PointingSnapshot:
        """Return an immutable snapshot. Called by UI and Stellarium threads."""
        with self._lock:
            return PointingSnapshot(
                ra_j2000=self._ra_j2000,
                dec_j2000=self._dec_j2000,
                roll=self._roll,
                matches=self._matches,
                prob=self._prob,
                last_success_timestamp=self._last_success_timestamp,
                valid=self._valid,
                all_centroids=self._all_centroids,
                matched_centroids=self._matched_centroids,
                image_size=self._image_size,
            )

    def clear_centroids(self) -> None:
        """Clear centroid data (e.g. on solve failure)."""
        with self._lock:
            self._all_centroids = None
            self._matched_centroids = None
            self._image_size = None

    def invalidate(self) -> None:
        """Mark state as invalid (e.g. on camera disconnect)."""
        with self._lock:
            self._valid = False
