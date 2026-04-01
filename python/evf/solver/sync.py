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

"""Sync calibration — rotation math and candidate star selection.

Computes the offset between camera and telescope optical axes using
body-frame sync: one sync point + Roll fully determines the 3-DOF
body-frame offset vector.  Two-phase flow:
  Phase A: plate-solve → build candidate list → auto-propose target
  Phase B: user confirms → body-frame correction applied to tracking
"""

from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation

EPS = 1e-12


# -- coordinate conversions --------------------------------------------------

def radec_to_vec(ra_deg: float, dec_deg: float) -> np.ndarray:
    """RA/Dec (degrees) → Cartesian unit vector."""
    ra, dec = np.radians(ra_deg), np.radians(dec_deg)
    return np.array([np.cos(dec) * np.cos(ra),
                     np.cos(dec) * np.sin(ra),
                     np.sin(dec)])


def vec_to_radec(v: np.ndarray) -> tuple[float, float]:
    """Cartesian unit vector → (RA_deg, Dec_deg)."""
    v = v / np.linalg.norm(v)
    dec = np.degrees(np.arcsin(np.clip(v[2], -1.0, 1.0)))
    ra = np.degrees(np.arctan2(v[1], v[0])) % 360.0
    return ra, dec


# -- body-frame sync (Roll-aware) --------------------------------------------

def orientation_from_radec_roll(
    ra_deg: float, dec_deg: float, roll_deg: float,
) -> Rotation:
    """Build camera orientation from plate-solve (RA, Dec, Roll).

    Returns Rotation T that maps body-frame vectors to celestial vectors.
    Body frame: X=left-in-image, Y=up-in-image, Z=boresight (right-handed).

    Roll convention matches tetra3 / navigation.py gnomonic_project:
    Roll=0 → image-up = celestial north, image-left = celestial east.
    Roll = angle from north to image-up, east of north.
    """
    ra = np.radians(ra_deg)
    dec = np.radians(dec_deg)
    roll = np.radians(roll_deg)

    # Boresight (pointing direction)
    boresight = np.array([
        np.cos(dec) * np.cos(ra),
        np.cos(dec) * np.sin(ra),
        np.sin(dec),
    ])

    # Celestial tangent plane directions at (RA, Dec)
    east = np.array([-np.sin(ra), np.cos(ra), 0.0])
    north = np.array([
        -np.sin(dec) * np.cos(ra),
        -np.sin(dec) * np.sin(ra),
        np.cos(dec),
    ])

    # Body axes in celestial coordinates, rotated by Roll
    cr, sr = np.cos(roll), np.sin(roll)
    body_x = east * cr - north * sr   # left in image
    body_y = east * sr + north * cr   # up in image
    body_z = boresight                # boresight

    return Rotation.from_matrix(np.column_stack([body_x, body_y, body_z]))


def compute_body_frame_sync(
    cam_ra: float,
    cam_dec: float,
    cam_roll: float,
    target_ra: float,
    target_dec: float,
) -> np.ndarray:
    """Compute body-frame sync vector from a single sync point.

    Returns d_body: the telescope main-scope direction expressed in the
    camera body frame.  This vector is constant regardless of where the
    telescope points (it depends only on the physical mounting).

    Args:
        cam_ra, cam_dec, cam_roll: Plate-solve result at sync time (degrees).
        target_ra, target_dec: Star the user centered in the eyepiece (degrees).

    Returns:
        Unit vector in the camera body frame.
    """
    T_sync = orientation_from_radec_roll(cam_ra, cam_dec, cam_roll)
    target_vec = radec_to_vec(target_ra, target_dec)
    d_body = T_sync.inv().apply(target_vec)
    return d_body


def apply_body_frame_sync(
    d_body: np.ndarray, ra: float, dec: float, roll: float,
) -> tuple[float, float]:
    """Apply body-frame sync correction using current plate-solve orientation.

    Args:
        d_body: Body-frame sync vector from compute_body_frame_sync.
        ra, dec, roll: Current plate-solve result (degrees).

    Returns:
        (corrected_ra, corrected_dec) — the telescope's true pointing.
    """
    T_current = orientation_from_radec_roll(ra, dec, roll)
    corrected = T_current.apply(d_body)
    return vec_to_radec(corrected)


# -- candidate selection ------------------------------------------------------

@dataclass
class SyncCandidate:
    """A matched star considered for sync calibration."""
    idx: int       # index into matched_centroids/matched_stars
    y: float       # pixel row
    x: float       # pixel column
    ra: float      # degrees
    dec: float     # degrees
    mag: float     # visual magnitude


def build_sync_candidates(
    matched_centroids: list,
    matched_stars: list,
    image_size: tuple[int, int],
    edge_margin_frac: float = 0.10,
    max_count: int = 25,
) -> list[SyncCandidate]:
    """Filter matched stars: discard edge stars, keep brightest N.

    Args:
        matched_centroids: List of [y, x] pixel coords from tetra3.
        matched_stars: List of [RA_deg, Dec_deg, mag] from tetra3.
        image_size: (height, width) of the solved image.
        edge_margin_frac: Fraction of image dimension to exclude at edges.
        max_count: Maximum candidates to return.

    Returns:
        List of SyncCandidate sorted by magnitude (brightest first).
    """
    h, w = image_size
    margin_y = h * edge_margin_frac
    margin_x = w * edge_margin_frac
    candidates = []
    for i, (centroid, star) in enumerate(zip(matched_centroids, matched_stars)):
        y, x = centroid[0], centroid[1]
        ra, dec, mag = star[0], star[1], star[2]
        if margin_x <= x <= w - margin_x and margin_y <= y <= h - margin_y:
            candidates.append(SyncCandidate(idx=i, y=y, x=x, ra=ra, dec=dec, mag=mag))
    candidates.sort(key=lambda c: c.mag)  # brightest first (lowest mag)
    return candidates[:max_count]


def auto_select(candidates: list[SyncCandidate], image_size: tuple[int, int]) -> int:
    """Pick the best candidate for automatic sync.

    Among the top candidates within 0.7 mag of the brightest, pick the
    one closest to the image center.

    Args:
        candidates: Non-empty list sorted by magnitude (brightest first).
        image_size: (height, width).

    Returns:
        Index into the candidates list.

    Raises:
        ValueError: If candidates is empty.
    """
    if not candidates:
        raise ValueError("No sync candidates available")
    cy, cx = image_size[0] / 2, image_size[1] / 2
    # Among the brightest (within 0.7 mag), pick closest to center
    top = [c for c in candidates if c.mag <= candidates[0].mag + 0.7]
    top.sort(key=lambda c: (c.x - cx) ** 2 + (c.y - cy) ** 2)
    return candidates.index(top[0])
