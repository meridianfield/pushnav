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

"""Tests for sync calibration: rotation math and candidate selection."""

import numpy as np
import pytest

from evf.solver.sync import (
    SyncCandidate,
    apply_body_frame_sync,
    auto_select,
    build_sync_candidates,
    compute_body_frame_sync,
    orientation_from_radec_roll,
    radec_to_vec,
    vec_to_radec,
)


# -- radec_to_vec / vec_to_radec roundtrip ------------------------------------


class TestCoordinateConversion:
    """Test RA/Dec ↔ Cartesian vector roundtrips."""

    @pytest.mark.parametrize(
        "ra, dec",
        [
            (0.0, 0.0),        # vernal equinox
            (90.0, 0.0),       # equator, 6h
            (180.0, 0.0),      # equator, 12h
            (270.0, 0.0),      # equator, 18h
            (0.0, 90.0),       # north celestial pole
            (0.0, -90.0),      # south celestial pole
            (45.0, 45.0),      # mid-latitude
            (123.456, -67.89), # arbitrary
            (359.99, 0.01),    # near RA=0 wrap
        ],
    )
    def test_roundtrip(self, ra, dec):
        v = radec_to_vec(ra, dec)
        ra2, dec2 = vec_to_radec(v)
        assert ra2 == pytest.approx(ra, abs=1e-10)
        assert dec2 == pytest.approx(dec, abs=1e-10)

    def test_unit_vector(self):
        """Output should be a unit vector."""
        v = radec_to_vec(42.0, 33.0)
        assert np.linalg.norm(v) == pytest.approx(1.0, abs=1e-15)

    def test_north_pole_vector(self):
        """North pole should be [0, 0, 1]."""
        v = radec_to_vec(0.0, 90.0)
        np.testing.assert_allclose(v, [0, 0, 1], atol=1e-15)

    def test_south_pole_vector(self):
        """South pole should be [0, 0, -1]."""
        v = radec_to_vec(0.0, -90.0)
        np.testing.assert_allclose(v, [0, 0, -1], atol=1e-15)


# -- build_sync_candidates ---------------------------------------------------


def _make_centroids_and_stars(n, image_size=(1000, 1500)):
    """Generate n matched centroids/stars spread across the image."""
    h, w = image_size
    centroids = []
    stars = []
    for i in range(n):
        # Spread evenly across the image
        y = h * (i + 1) / (n + 1)
        x = w * (i + 1) / (n + 1)
        centroids.append([y, x])
        stars.append([100.0 + i * 0.5, 30.0 + i * 0.1, 3.0 + i * 0.2])
    return centroids, stars


class TestBuildSyncCandidates:
    """Test sync candidate filtering and sorting."""

    def test_basic(self):
        centroids, stars = _make_centroids_and_stars(10)
        result = build_sync_candidates(centroids, stars, (1000, 1500))
        assert len(result) <= 10
        assert all(isinstance(c, SyncCandidate) for c in result)

    def test_edge_filtering(self):
        """Stars near edges should be excluded."""
        centroids = [[5, 750], [500, 5], [500, 750], [995, 750], [500, 1495]]
        stars = [[100, 30, 3.0]] * 5
        result = build_sync_candidates(centroids, stars, (1000, 1500))
        # Only the center star should pass (5 and 995 are within 10% margin of 1000)
        assert len(result) == 1
        assert result[0].y == 500 and result[0].x == 750

    def test_brightness_sort(self):
        """Candidates should be sorted by magnitude (brightest first)."""
        centroids = [[500, 500], [500, 700], [500, 900]]
        stars = [[100, 30, 5.0], [101, 31, 2.0], [102, 32, 8.0]]
        result = build_sync_candidates(centroids, stars, (1000, 1500))
        mags = [c.mag for c in result]
        assert mags == sorted(mags)
        assert result[0].mag == 2.0

    def test_max_count(self):
        """Should respect max_count limit."""
        centroids, stars = _make_centroids_and_stars(50)
        result = build_sync_candidates(
            centroids, stars, (1000, 1500), max_count=10
        )
        assert len(result) <= 10

    def test_empty_input(self):
        result = build_sync_candidates([], [], (1000, 1500))
        assert result == []


# -- auto_select --------------------------------------------------------------


class TestAutoSelect:
    """Test automatic candidate selection."""

    def test_picks_brightest(self):
        """Should pick the brightest star."""
        candidates = [
            SyncCandidate(0, 500, 500, 100.0, 30.0, 5.0),
            SyncCandidate(1, 400, 400, 101.0, 31.0, 2.0),  # brightest
            SyncCandidate(2, 600, 600, 102.0, 32.0, 8.0),
        ]
        # Sort by mag as build_sync_candidates does
        candidates.sort(key=lambda c: c.mag)
        idx = auto_select(candidates, (1000, 1500))
        assert candidates[idx].mag == 2.0

    def test_tiebreak_by_center(self):
        """Among equally bright stars, should prefer closest to center."""
        candidates = [
            SyncCandidate(0, 500, 750, 100.0, 30.0, 3.0),  # center
            SyncCandidate(1, 200, 200, 101.0, 31.0, 3.0),  # far from center
        ]
        candidates.sort(key=lambda c: c.mag)
        idx = auto_select(candidates, (1000, 1500))
        selected = candidates[idx]
        assert selected.y == 500 and selected.x == 750

    def test_within_mag_threshold(self):
        """Should consider stars within 0.7 mag of brightest for center tie-break."""
        candidates = [
            SyncCandidate(0, 200, 200, 100.0, 30.0, 3.0),  # brightest, far
            SyncCandidate(1, 500, 750, 101.0, 31.0, 3.5),  # 0.5 mag dimmer, center
            SyncCandidate(2, 500, 750, 102.0, 32.0, 5.0),  # too dim for tie-break
        ]
        candidates.sort(key=lambda c: c.mag)
        idx = auto_select(candidates, (1000, 1500))
        selected = candidates[idx]
        # Should pick the center one (mag 3.5) since it's within 0.7 of 3.0
        assert selected.mag == 3.5

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No sync candidates"):
            auto_select([], (1000, 1500))


# -- body-frame sync (Roll-aware) ---------------------------------------------


class TestBodyFrameSync:
    """Test that body-frame sync (using Roll) is accurate everywhere."""

    def test_roundtrip_at_sync_point(self):
        """Body-frame sync is exact at the calibration point."""
        cam_ra, cam_dec, cam_roll = 100.0, 30.0, 15.0
        target_ra, target_dec = 102.0, 31.0

        d_body = compute_body_frame_sync(
            cam_ra, cam_dec, cam_roll, target_ra, target_dec
        )
        ra_out, dec_out = apply_body_frame_sync(
            d_body, cam_ra, cam_dec, cam_roll
        )

        assert ra_out == pytest.approx(target_ra, abs=1e-8)
        assert dec_out == pytest.approx(target_dec, abs=1e-8)

    def test_handles_roll_change(self):
        """Sync at Roll=0, apply at Roll=180 (meridian flip), still accurate.

        The body-frame offset is constant in the tube frame.  We simulate
        the telescope at a known offset, sync with one Roll, then verify
        at a completely different Roll value.
        """
        # Simulate a fixed body-frame offset: target is 2° to the right
        # and 1° up from the camera boresight
        sync_ra, sync_dec, sync_roll = 90.0, 45.0, 0.0
        T_sync = orientation_from_radec_roll(sync_ra, sync_dec, sync_roll)
        # Body-frame offset: slightly off-axis
        d_body_true = np.array([0.02, 0.01, 1.0])
        d_body_true /= np.linalg.norm(d_body_true)
        # Target in celestial coords at sync time
        target_vec = T_sync.apply(d_body_true)
        target_ra, target_dec = vec_to_radec(target_vec)

        # Compute body-frame sync from the sync point
        d_body = compute_body_frame_sync(
            sync_ra, sync_dec, sync_roll, target_ra, target_dec
        )
        np.testing.assert_allclose(d_body, d_body_true, atol=1e-10)

        # Now apply at a different position and Roll=180 (meridian flip)
        track_ra, track_dec, track_roll = 200.0, -30.0, 180.0
        T_track = orientation_from_radec_roll(track_ra, track_dec, track_roll)
        expected_vec = T_track.apply(d_body_true)
        expected_ra, expected_dec = vec_to_radec(expected_vec)

        out_ra, out_dec = apply_body_frame_sync(
            d_body, track_ra, track_dec, track_roll
        )
        assert out_ra == pytest.approx(expected_ra, abs=1e-8)
        assert out_dec == pytest.approx(expected_dec, abs=1e-8)

    def test_accuracy_across_sky(self):
        """Sync at one position, test at 20 sky points with varying Roll."""
        # Sync configuration
        sync_ra, sync_dec, sync_roll = 80.0, 40.0, 25.0
        T_sync = orientation_from_radec_roll(sync_ra, sync_dec, sync_roll)
        # Fixed body-frame offset
        d_body_true = np.array([-0.015, 0.025, 1.0])
        d_body_true /= np.linalg.norm(d_body_true)
        target_vec = T_sync.apply(d_body_true)
        target_ra, target_dec = vec_to_radec(target_vec)

        d_body = compute_body_frame_sync(
            sync_ra, sync_dec, sync_roll, target_ra, target_dec
        )

        # Test at 20 positions with various Roll values
        test_points = [
            (0, 0, 0), (45, 30, 90), (90, 60, 180), (135, -30, 270),
            (180, -60, 45), (225, 45, 135), (270, -45, 225), (315, 15, 315),
            (30, 89, 10), (200, -89, 350), (96, -53, 120), (79, 46, 240),
            (280, 0, 60), (10, -80, 150), (180, 80, 300), (96, 46, 30),
            (280, -53, 170), (259, 53, 200), (350, 10, 85), (120, -20, 330),
        ]
        max_error = 0.0
        for ra, dec, roll in test_points:
            T = orientation_from_radec_roll(ra, dec, roll)
            expected = vec_to_radec(T.apply(d_body_true))
            got = apply_body_frame_sync(d_body, ra, dec, roll)

            v_exp = radec_to_vec(*expected)
            v_got = radec_to_vec(*got)
            err = np.degrees(
                np.arccos(np.clip(np.dot(v_exp, v_got), -1, 1))
            )
            max_error = max(max_error, err)
            assert err < 0.001, (
                f"Error at ({ra}, {dec}, roll={roll}): {err:.6f}°"
            )
        assert max_error < 0.001, f"Max error across sky: {max_error:.6f}°"

    def test_canopus_capella_consistency(self):
        """Simulate sync at Canopus, verify correction at Capella with Roll change.

        This models the real scenario: sync near one star, then slew to
        the opposite side of the sky (with Roll changing due to tube rotation).
        Body-frame sync should remain accurate.
        """
        canopus_ra, canopus_dec = 95.988, -52.696
        capella_ra, capella_dec = 79.172, 45.998

        # Camera body-frame offset (fixed physical mounting)
        d_body_true = np.array([0.03, -0.02, 1.0])
        d_body_true /= np.linalg.norm(d_body_true)

        # Sync at Canopus with Roll=15°
        sync_roll = 15.0
        T_sync = orientation_from_radec_roll(canopus_ra, canopus_dec, sync_roll)
        # Camera boresight points at Canopus; telescope (d_body_true) points at:
        sync_target_vec = T_sync.apply(d_body_true)
        sync_target_ra, sync_target_dec = vec_to_radec(sync_target_vec)

        # Compute body-frame sync
        d_body = compute_body_frame_sync(
            canopus_ra, canopus_dec, sync_roll,
            sync_target_ra, sync_target_dec,
        )

        # Now tracking near Capella with Roll=195° (large Roll change)
        track_roll = 195.0
        T_track = orientation_from_radec_roll(capella_ra, capella_dec, track_roll)
        expected_vec = T_track.apply(d_body_true)
        expected_ra, expected_dec = vec_to_radec(expected_vec)

        got_ra, got_dec = apply_body_frame_sync(
            d_body, capella_ra, capella_dec, track_roll
        )

        v_exp = radec_to_vec(expected_ra, expected_dec)
        v_got = radec_to_vec(got_ra, got_dec)
        err = np.degrees(np.arccos(np.clip(np.dot(v_exp, v_got), -1, 1)))

        assert err < 0.001, (
            f"Error at Capella with Roll change: {err:.6f}° "
            f"(expected < 0.001°)"
        )
