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

"""Tests for navigation math functions."""

import math

import pytest

from evf.engine.navigation import (
    angular_separation,
    compute_navigation,
    edge_arrow_position,
    gnomonic_project,
    sky_position_angle,
)


# ---------------------------------------------------------------------------
# angular_separation
# ---------------------------------------------------------------------------

class TestAngularSeparation:
    def test_zero_distance(self):
        assert angular_separation(10.0, 20.0, 10.0, 20.0) == pytest.approx(0.0, abs=1e-10)

    def test_one_degree_in_dec(self):
        assert angular_separation(0.0, 0.0, 0.0, 1.0) == pytest.approx(1.0, abs=1e-10)

    def test_one_degree_in_ra_at_equator(self):
        assert angular_separation(0.0, 0.0, 1.0, 0.0) == pytest.approx(1.0, abs=1e-10)

    def test_ra_foreshortening_at_dec60(self):
        """1° RA at Dec=60° should be ~0.5° separation (cos(60°)=0.5)."""
        sep = angular_separation(0.0, 60.0, 1.0, 60.0)
        assert sep == pytest.approx(0.5, abs=0.01)

    def test_pole_to_pole(self):
        assert angular_separation(0.0, 90.0, 0.0, -90.0) == pytest.approx(180.0, abs=1e-8)

    def test_symmetry(self):
        s1 = angular_separation(10.0, 20.0, 30.0, 40.0)
        s2 = angular_separation(30.0, 40.0, 10.0, 20.0)
        assert s1 == pytest.approx(s2, abs=1e-10)

    def test_ra_wrap_around(self):
        """Separation across RA=0/360 boundary."""
        sep = angular_separation(359.0, 0.0, 1.0, 0.0)
        assert sep == pytest.approx(2.0, abs=1e-8)

    def test_large_separation(self):
        """Opposite points on equator = 180°."""
        sep = angular_separation(0.0, 0.0, 180.0, 0.0)
        assert sep == pytest.approx(180.0, abs=1e-8)


# ---------------------------------------------------------------------------
# sky_position_angle
# ---------------------------------------------------------------------------

class TestSkyPositionAngle:
    def test_due_north(self):
        """Target 1° north → PA = 0°."""
        pa = sky_position_angle(0.0, 0.0, 0.0, 1.0)
        assert pa == pytest.approx(0.0, abs=0.1)

    def test_due_south(self):
        """Target 1° south → PA = 180°."""
        pa = sky_position_angle(0.0, 0.0, 0.0, -1.0)
        assert pa == pytest.approx(180.0, abs=0.1)

    def test_due_east(self):
        """Target 1° east in RA at equator → PA = 90°."""
        pa = sky_position_angle(0.0, 0.0, 1.0, 0.0)
        assert pa == pytest.approx(90.0, abs=0.1)

    def test_due_west(self):
        """Target 1° west in RA at equator → PA = 270°."""
        pa = sky_position_angle(1.0, 0.0, 0.0, 0.0)
        assert pa == pytest.approx(270.0, abs=0.1)

    def test_result_range(self):
        """PA should always be in [0, 360)."""
        for ra1, dec1, ra2, dec2 in [
            (0, 0, 1, 1), (350, 80, 10, -80), (180, -45, 0, 45),
        ]:
            pa = sky_position_angle(ra1, dec1, ra2, dec2)
            assert 0 <= pa < 360


# ---------------------------------------------------------------------------
# gnomonic_project
# ---------------------------------------------------------------------------

class TestGnomonicProject:
    def test_target_at_center(self):
        """Target at boresight → image center."""
        px, py = gnomonic_project(10.0, 20.0, 0.0, 10.0, 20.0, 10.0, 640, 480)
        assert px == pytest.approx(320.0, abs=0.1)
        assert py == pytest.approx(240.0, abs=0.1)

    def test_target_north_at_roll0(self):
        """Target 1° north at Roll=0 → above center (smaller y)."""
        result = gnomonic_project(0.0, 45.0, 0.0, 0.0, 46.0, 10.0, 640, 480)
        assert result is not None
        px, py = result
        assert px == pytest.approx(320.0, abs=1.0)  # centered horizontally
        assert py < 240.0  # above center

    def test_target_east_at_roll0(self):
        """Target 1° east at Roll=0 → left of center (pinhole mirror: east→left)."""
        result = gnomonic_project(0.0, 0.0, 0.0, 1.0, 0.0, 10.0, 640, 480)
        assert result is not None
        px, py = result
        assert px < 320.0  # left of center
        assert py == pytest.approx(240.0, abs=1.0)  # centered vertically

    def test_behind_camera(self):
        """Target >90° away → None."""
        result = gnomonic_project(0.0, 0.0, 0.0, 180.0, 0.0, 10.0, 640, 480)
        assert result is None

    def test_roll90_rotates(self):
        """Roll=90 should rotate: target north → appears to the right."""
        result_r0 = gnomonic_project(0.0, 45.0, 0.0, 0.0, 46.0, 10.0, 640, 480)
        result_r90 = gnomonic_project(0.0, 45.0, 90.0, 0.0, 46.0, 10.0, 640, 480)
        assert result_r0 is not None and result_r90 is not None
        # At roll=0, target is above center (py < 240)
        assert result_r0[1] < 240.0
        # At roll=90, target should be to the right (px > 320)
        assert result_r90[0] > 320.0

    def test_fov_scaling(self):
        """Wider FOV → target closer to center in pixels."""
        result_narrow = gnomonic_project(0.0, 45.0, 0.0, 0.0, 46.0, 5.0, 640, 480)
        result_wide = gnomonic_project(0.0, 45.0, 0.0, 0.0, 46.0, 20.0, 640, 480)
        assert result_narrow is not None and result_wide is not None
        # Narrower FOV → target further from center in pixels
        dist_narrow = abs(result_narrow[1] - 240.0)
        dist_wide = abs(result_wide[1] - 240.0)
        assert dist_narrow > dist_wide


# ---------------------------------------------------------------------------
# compute_navigation
# ---------------------------------------------------------------------------

class TestComputeNavigation:
    def test_target_north_roll0(self):
        """Target due north at Roll=0 → delta_up > 0, delta_right ≈ 0."""
        nav = compute_navigation(0.0, 45.0, 0.0, 0.0, 46.0, 10.0, 640, 480)
        assert nav.separation_deg == pytest.approx(1.0, abs=0.01)
        assert nav.delta_up_deg > 0.5
        assert abs(nav.delta_right_deg) < 0.1
        assert nav.camera_angle_deg == pytest.approx(0.0, abs=1.0)

    def test_direction_text_format(self):
        """direction_text should contain R/L and U/D indicators."""
        nav = compute_navigation(0.0, 45.0, 0.0, 1.0, 46.0, 10.0, 640, 480)
        assert "\u00b0" in nav.direction_text
        assert any(d in nav.direction_text for d in ["R", "L"])
        assert any(d in nav.direction_text for d in ["U", "D"])

    def test_in_fov_when_close(self):
        """Target within FOV should have in_fov=True."""
        nav = compute_navigation(0.0, 45.0, 0.0, 0.0, 45.5, 10.0, 640, 480)
        assert nav.in_fov is True
        assert nav.pixel_x is not None
        assert nav.pixel_y is not None

    def test_not_in_fov_when_far(self):
        """Target outside FOV should have in_fov=False."""
        nav = compute_navigation(0.0, 45.0, 0.0, 0.0, 60.0, 10.0, 640, 480)
        assert nav.in_fov is False

    def test_behind_camera(self):
        """Target behind camera → pixel coords None."""
        nav = compute_navigation(0.0, 0.0, 0.0, 180.0, 0.0, 10.0, 640, 480)
        assert nav.pixel_x is None
        assert nav.pixel_y is None
        assert nav.in_fov is False


# ---------------------------------------------------------------------------
# edge_arrow_position
# ---------------------------------------------------------------------------

class TestEdgeArrowPosition:
    def test_target_far_right(self):
        """Target far to the right → arrow on right edge."""
        x, y, angle = edge_arrow_position(10000.0, 240.0, 640, 480)
        assert x == pytest.approx(620.0, abs=1.0)  # right edge with margin
        assert y == pytest.approx(240.0, abs=1.0)  # centered vertically
        assert angle == pytest.approx(90.0, abs=1.0)

    def test_target_far_above(self):
        """Target far above → arrow on top edge."""
        x, y, angle = edge_arrow_position(320.0, -10000.0, 640, 480)
        assert y == pytest.approx(20.0, abs=1.0)  # top edge with margin
        assert x == pytest.approx(320.0, abs=1.0)
        assert angle == pytest.approx(0.0, abs=1.0)

    def test_target_far_left(self):
        """Target far to the left → arrow on left edge."""
        x, y, angle = edge_arrow_position(-10000.0, 240.0, 640, 480)
        assert x == pytest.approx(20.0, abs=1.0)  # left edge with margin
        assert angle == pytest.approx(270.0, abs=1.0)

    def test_target_far_below(self):
        """Target far below → arrow on bottom edge."""
        x, y, angle = edge_arrow_position(320.0, 10000.0, 640, 480)
        assert y == pytest.approx(460.0, abs=1.0)  # bottom edge with margin
        assert angle == pytest.approx(180.0, abs=1.0)

    def test_diagonal_target(self):
        """Target at 45° should hit a corner area."""
        x, y, angle = edge_arrow_position(10000.0, -10000.0, 640, 480)
        # Should be on right or top edge
        assert x >= 20 and y >= 20
        # Angle should be around 45° (up-right)
        assert 0 < angle < 90
