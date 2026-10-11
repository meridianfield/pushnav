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

"""Independent checks of the sync rotation maths.

test_sync.py builds its expected values with orientation_from_radec_roll,
the function under test, so a consistent error there would go unnoticed.
These tests don't depend on it:

- reference values recorded from the earlier scipy
  (scipy.spatial.transform.Rotation) implementation of solver/sync.py, at
  the commit before 65ccf7d;
- geometric properties of the orientation matrix checked against
  radec_to_vec and the documented roll convention.
"""

import numpy as np
import pytest

from evf.solver.sync import (
    apply_body_frame_sync,
    compute_body_frame_sync,
    orientation_from_radec_roll,
    radec_to_vec,
)

# (cam_ra, cam_dec, cam_roll, target_ra, target_dec, track_ra, track_dec, track_roll),
# (d_body), (corrected_ra, corrected_dec) — all degrees.
_SCIPY_REFERENCE = [
    # Orion -> Sirius, roll 0
    ((83.82, -5.39, 0.0, 84.05, -5.1, 101.29, -16.72, 0.0),
     (0.003998354359151461, 0.005060679374136053, 0.9999792011270486),
     (101.52884226502155, -16.429905819931932)),
    # Vega -> Altair
    ((279.23, 38.78, 37.5, 279.8, 38.2, 297.7, 8.87, -12.0),
     (0.012349838724360563, -0.0032523649381217216, 0.9999184484775705),
     (298.4396696093825, 8.834114884004448)),
    # same pointing, roll -95 == 265: must return the sync target itself
    ((10.68, 41.27, -95.0, 11.1, 40.9, 10.68, 41.27, 265.0),
     (-0.0069026549435640015, -0.004957906003509028, 0.9999638856092706),
     (11.100000000000003, 40.900000000000006)),
    # RA 0/360 seam
    ((359.8, 0.0, 180.0, 0.4, 0.3, 0.2, -0.1, -180.0),
     (-0.010471640571620124, -0.005235963831419524, 0.9999314623645436),
     (0.7999954307593531, 0.20000548301890714)),
    # near the north pole
    ((0.0, 89.9, 45.0, 120.0, 89.5, 250.0, 88.0, 300.0),
     (0.00102451175301511, 0.009663267843634965, 0.9999527847004828),
     (234.93230399407454, 88.26817307575821)),
    # sync star at the boresight: d_body = +Z, output = tracking pointing
    ((37.95, 89.26, 0.0, 37.95, 89.26, 210.0, -89.7, 10.0),
     (-1.1686008192898581e-18, 8.983110794374208e-20, 1.0),
     (210.0, -89.7000000000007)),
    # Canopus -> Capella, across the sky
    ((95.99, -52.7, 12.0, 96.8, -51.6, 79.17, 45.99, -170.0),
     (0.0046079848977187985, 0.02055530391659398, 0.9997780983578699),
     (78.51449752465996, 44.87402480757946)),
    # sync star ~3.6 deg off-axis
    ((201.3, -11.16, 359.9, 203.0, -8.0, 30.0, 60.0, 0.1),
     (0.02947355252018377, 0.05498873123509969, 0.9980518769778425),
     (33.747466906043705, 63.10118452475948)),
    # roll given as multiples of 360
    ((150.0, -30.0, -720.0, 151.0, -29.0, 300.0, 20.0, 540.0),
     (0.015264218607054365, 0.01738580202842684, 0.9997323329362434),
     (299.0749830960119, 19.001401708155043)),
]


def _separation_deg(ra1, dec1, ra2, dec2) -> float:
    """Angle between two sky positions (well-defined at the poles, unlike ΔRA).

    atan2(|a×b|, a·b) rather than arccos(a·b): arccos can't resolve angles
    below ~sqrt(2·eps) ≈ 8.5e-7 deg.
    """
    a, b = radec_to_vec(ra1, dec1), radec_to_vec(ra2, dec2)
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b))))


@pytest.mark.parametrize("inputs,d_body_ref,radec_ref", _SCIPY_REFERENCE)
def test_matches_scipy_reference(inputs, d_body_ref, radec_ref):
    cam_ra, cam_dec, cam_roll, tgt_ra, tgt_dec, trk_ra, trk_dec, trk_roll = inputs
    d_body = compute_body_frame_sync(cam_ra, cam_dec, cam_roll, tgt_ra, tgt_dec)
    np.testing.assert_allclose(d_body, d_body_ref, rtol=0, atol=1e-12)

    ra, dec = apply_body_frame_sync(np.array(d_body_ref), trk_ra, trk_dec, trk_roll)
    # 1e-7 deg = 0.36 mas. Near the poles arcsin(z) limits precision to a few mas
    # for *any* implementation, so compare positions, not raw RA.
    assert _separation_deg(ra, dec, *radec_ref) < 1e-7


# -- geometric properties of the orientation matrix ---------------------------

_rng = np.random.default_rng(20261006)
_RANDOM_POINTINGS = list(zip(
    _rng.uniform(0, 360, 500),
    _rng.uniform(-90, 90, 500),
    _rng.uniform(-720, 720, 500),
))


def test_orientation_is_a_proper_rotation():
    for ra, dec, roll in _RANDOM_POINTINGS:
        T = orientation_from_radec_roll(ra, dec, roll)
        np.testing.assert_allclose(T.T @ T, np.eye(3), rtol=0, atol=1e-12)
        assert abs(np.linalg.det(T) - 1.0) < 1e-12  # rotation, not reflection


def test_boresight_column_is_the_pointing_direction():
    for ra, dec, roll in _RANDOM_POINTINGS:
        T = orientation_from_radec_roll(ra, dec, roll)
        np.testing.assert_allclose(T[:, 2], radec_to_vec(ra, dec), rtol=0, atol=1e-12)


@pytest.mark.parametrize("ra,dec", [(0.0, 0.0), (83.8, -5.4), (279.2, 38.8), (200.0, -60.0)])
def test_roll_convention(ra, dec):
    """Roll 0: image-up = north, image-left = east. Roll 90: image-up = east."""
    r, d = np.radians(ra), np.radians(dec)
    east = np.array([-np.sin(r), np.cos(r), 0.0])
    north = np.array([-np.sin(d) * np.cos(r), -np.sin(d) * np.sin(r), np.cos(d)])

    T0 = orientation_from_radec_roll(ra, dec, 0.0)
    np.testing.assert_allclose(T0[:, 1], north, atol=1e-12)  # body Y = image-up
    np.testing.assert_allclose(T0[:, 0], east, atol=1e-12)   # body X = image-left

    T90 = orientation_from_radec_roll(ra, dec, 90.0)
    np.testing.assert_allclose(T90[:, 1], east, atol=1e-12)


def test_roll_is_periodic():
    for ra, dec, roll in _RANDOM_POINTINGS[:50]:
        np.testing.assert_allclose(
            orientation_from_radec_roll(ra, dec, roll),
            orientation_from_radec_roll(ra, dec, roll + 360.0),
            rtol=0, atol=1e-12,
        )
