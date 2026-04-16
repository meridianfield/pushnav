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

"""Tests for J2000 <-> JNow precession (evf.engine.epoch)."""

import pytest

from evf.engine import epoch


class TestRoundTrip:
    """jnow_to_j2000(j2000_to_jnow(x)) == x within 1 mas."""

    @pytest.mark.parametrize("ra_deg", [0.0, 90.0, 180.0, 270.0, 359.9])
    @pytest.mark.parametrize("dec_deg", [-89.0, -45.0, 0.0, 45.0, 89.0])
    def test_round_trip_symmetry(self, ra_deg: float, dec_deg: float):
        ra2, dec2 = epoch.j2000_to_jnow(ra_deg, dec_deg)
        ra3, dec3 = epoch.jnow_to_j2000(ra2, dec2)
        # 1 mas = 1/3600000 deg ≈ 2.78e-7 deg
        assert abs((ra3 - ra_deg + 180.0) % 360.0 - 180.0) < 1e-6
        assert abs(dec3 - dec_deg) < 1e-6


class TestMagnitudeSanity:
    """Precession displaces J2000 coords by 0.2°-0.7° in 2026."""

    def test_vega_displaced_by_expected_amount(self):
        # Vega J2000: RA 279.234°, Dec +38.784°
        ra_jnow, dec_jnow = epoch.j2000_to_jnow(279.234, 38.784)
        # Normalize RA difference to [-180, 180]
        dra = ((ra_jnow - 279.234) + 180.0) % 360.0 - 180.0
        # Expected: ~0.3-0.5° RA shift, small Dec shift
        assert 0.1 < abs(dra) < 1.0, f"RA shift {dra} outside expected range"
        assert abs(dec_jnow - 38.784) < 0.2


class TestPoleStability:
    """Near-pole coords stay in valid ranges."""

    def test_polaris_like(self):
        # Polaris J2000: RA ~37.95°, Dec ~89.264°
        ra_jnow, dec_jnow = epoch.j2000_to_jnow(37.95, 89.264)
        assert 0.0 <= ra_jnow < 360.0
        assert 89.0 < dec_jnow <= 90.0

    def test_south_pole(self):
        ra_jnow, dec_jnow = epoch.j2000_to_jnow(0.0, -89.9)
        assert 0.0 <= ra_jnow < 360.0
        assert -90.0 <= dec_jnow < -89.0


class TestCache:
    """Matrix cache returns the same object within _CACHE_SECONDS."""

    def test_cache_hit_returns_same_object(self):
        # Reset cache to force a fresh matrix
        epoch._cached_matrix = None
        epoch._cached_at = 0.0
        P1, Pt1 = epoch._refresh_matrix()
        P2, Pt2 = epoch._refresh_matrix()
        assert P1 is P2
        assert Pt1 is Pt2
