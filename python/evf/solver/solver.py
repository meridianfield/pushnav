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

"""Plate solver — tetra3rs wrapper for single-frame plate solving.

Internals use the Rust-backed tetra3rs (MIT, GPL-3 compatible). The
external API and result-dict shape match the legacy tetra3 wrapper so
the rest of the engine is unchanged. See
docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md for the
parameter rationale and tetra3rs API quirks.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import numpy as np
import tetra3rs
from PIL import Image

from evf.paths import tetra3rs_database_path

logger = logging.getLogger(__name__)

_DATABASE_PATH = tetra3rs_database_path()

# Centroid extraction parameters — see the bench-findings doc for why
# matched_filter_sigma=2.0 is load-bearing (without it, M42 nebulosity
# crowds out real stars in the brightest-N list and orion.png fails).
_CENTROID_PARAMS = dict(
    sigma_threshold=5.0,
    max_pixels=2000,
    max_centroids=30,
    matched_filter_sigma=2.0,
)

_FOV_DEG = 8.86
_FOV_MAX_ERROR_DEG = 1.5


class PlateSolver:
    """Load tetra3rs database once and solve frames on demand."""

    def __init__(self, database_path: Path | None = None) -> None:
        db_path = database_path or _DATABASE_PATH
        t0 = time.monotonic()
        self._db = tetra3rs.SolverDatabase.load_from_file(str(db_path))
        elapsed = time.monotonic() - t0
        logger.info(
            "tetra3rs database loaded in %.2fs: %s (%d stars, %d patterns)",
            elapsed, db_path, self._db.num_stars, self._db.num_patterns,
        )

    def solve_frame(self, image_bytes: bytes) -> dict:
        """Solve a single image frame. Returns a tetra3-compatible result dict.

        Keys returned (preserving the legacy contract):
          RA, Dec, Roll          — degrees, J2000
          Matches                — number of matched stars (int)
          Prob                   — false-positive probability (float)
          T_extract              — centroid extraction time, ms
          T_solve                — solver internal time, ms
          all_centroids          — list[[y, x], ...] top-left-origin pixels
          matched_centroids      — list[[y, x], ...] top-left-origin pixels
          matched_stars          — list[[ra_deg, dec_deg, mag], ...]
          image_size             — (height, width)

        On unsolvable frames, RA/Dec/Roll are None, Matches=0, Prob=None,
        and the matched_* lists are empty. all_centroids is populated
        when extraction succeeded regardless of whether the solve did.
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        arr = np.asarray(img, dtype=np.float64)
        h, w = arr.shape

        t0 = time.monotonic()
        extraction = tetra3rs.extract_centroids(arr, **_CENTROID_PARAMS)
        t_extract_ms = (time.monotonic() - t0) * 1000

        all_centroids = self._centroids_list_to_yx(extraction.centroids, h, w)

        t0 = time.monotonic()
        result = self._db.solve_from_centroids(
            extraction.centroids,
            fov_estimate_deg=_FOV_DEG,
            fov_max_error_deg=_FOV_MAX_ERROR_DEG,
            image_shape=(h, w),
        )
        t_solve_ms = (time.monotonic() - t0) * 1000

        out: dict = {
            "RA": None,
            "Dec": None,
            "Roll": None,
            "Matches": 0,
            "Prob": None,
            "T_extract": t_extract_ms,
            "T_solve": t_solve_ms,
            "all_centroids": all_centroids,
            "matched_centroids": [],
            "matched_stars": [],
            "image_size": (h, w),
        }

        # result.status is a plain str from the pyo3 binding (not a Python
        # Enum); tetra3rs exposes no SolveStatus type at module level.
        if result is None or result.status != "match_found":
            return out

        # Roll convention: tetra3rs roll_deg is ~180° flipped from the
        # legacy evf result (which negated tetra3's Roll as `360 - r`).
        # Empirically verified across the five test samples.
        roll = (result.roll_deg + 180.0) % 360.0

        # result.matched_centroids is a numpy array of indices into
        # extraction.centroids (not Centroid objects).
        matched_centroids = self._indices_to_yx(
            result.matched_centroids, extraction.centroids, h, w
        )
        matched_stars = self._catalog_ids_to_radec_mag(result.matched_catalog_ids)

        out.update({
            "RA": result.ra_deg,
            "Dec": result.dec_deg,
            "Roll": roll,
            "Matches": result.num_matches or 0,
            "Prob": result.probability,
            "matched_centroids": matched_centroids,
            "matched_stars": matched_stars,
        })
        return out

    def _centroids_list_to_yx(self, centroids, h: int, w: int) -> list:
        """Convert a list of tetra3rs Centroid objects (image-center origin,
        +X right, +Y down) to legacy [y, x] top-left-origin pixel coords."""
        cx, cy = w / 2.0, h / 2.0
        return [
            [float(c.y + cy), float(c.x + cx)]
            for c in centroids
        ]

    def _indices_to_yx(self, indices, centroids, h: int, w: int) -> list:
        """Look up matched centroid indices in the extraction list and
        return legacy [y, x] top-left-origin pixel coords."""
        cx, cy = w / 2.0, h / 2.0
        out = []
        for idx in indices:
            c = centroids[int(idx)]
            out.append([float(c.y + cy), float(c.x + cx)])
        return out

    def _catalog_ids_to_radec_mag(self, ids) -> list:
        """Build the legacy [[ra_deg, dec_deg, mag], ...] list from
        tetra3rs Gaia source IDs via db.get_star_by_id().

        Note: CatalogStar exposes .magnitude (not .mag); we normalise to
        'mag' in the returned tuple to match the legacy contract.
        """
        out = []
        for sid in ids:
            star = self._db.get_star_by_id(sid)
            out.append([float(star.ra_deg), float(star.dec_deg), float(star.magnitude)])
        return out

    @staticmethod
    def is_valid(
        result: dict, min_matches: int = 8, max_prob: float = 0.2
    ) -> bool:
        """Check if a solve result meets quality thresholds."""
        if result.get("RA") is None:
            return False
        if result.get("Matches", 0) < min_matches:
            return False
        if result.get("Prob", 1.0) > max_prob:
            return False
        return True
