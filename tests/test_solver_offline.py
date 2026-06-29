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

"""Tests for plate solver and solver thread (Phase 6).

Offline solve tests per ACCEPTANCE_TESTS.md §J1–J2 and impl0.md §6.5.
Solver thread tests per impl0.md §6.4 verification criteria.
"""

import io
import time
from pathlib import Path

import pytest
from PIL import Image

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.pointing import PointingState
from evf.engine.state import EngineState, StateMachine
from evf.solver.solver import PlateSolver
from evf.solver.thread import SolverThread

_SAMPLES_DIR = Path(__file__).parent / "samples"

# solver fixture is provided by conftest.py (session-scoped)


# ---------------------------------------------------------------------------
# Offline image solving (§6.5 / ACCEPTANCE_TESTS §J1–J2)
# ---------------------------------------------------------------------------


class TestOfflineSolve:
    @pytest.mark.parametrize(
        "image_name,expected_ra,expected_dec",
        [
            ("a.png", 79.025, 46.762),
            ("b.png", 132.88, 46.37),
            ("c.png", 49.76, 57.84),
            ("d.png", 30.83, 49.19),
        ],
    )
    def test_solve_image(self, solver, image_name, expected_ra, expected_dec):
        """Solve sample image and verify RA/Dec within 2 degrees."""
        image_bytes = (_SAMPLES_DIR / image_name).read_bytes()
        result = solver.solve_frame(image_bytes)

        assert result["RA"] is not None, f"{image_name}: solve failed"
        assert abs(result["RA"] - expected_ra) < 2, f"{image_name}: RA off"
        assert abs(result["Dec"] - expected_dec) < 2, f"{image_name}: Dec off"
        assert result["Matches"] >= 8, f"{image_name}: too few matches"
        assert result["Prob"] <= 0.2, f"{image_name}: probability too high"


# ---------------------------------------------------------------------------
# Roll-convention regression (tetra3rs ↔ sync.py body-frame formulas)
# ---------------------------------------------------------------------------


class TestRollRegression:
    """Lock in the Roll convention. tetra3rs roll_deg is 180° flipped
    from tetra3's negated convention; the wrapper corrects to match
    the body-frame formulas in solver/sync.py. A sign error here is
    silent until sync calibration fails on real hardware.
    """

    # Values captured from the tetra3rs wrapper at port time.
    # Tolerance is loose (5°) because RA/Dec refinement also nudges
    # Roll; what we're really testing is the convention sign, not
    # exact arithmetic.
    @pytest.mark.parametrize(
        "image_name,expected_roll",
        [
            ("a.png", 202.045),
            ("b.png", 268.818),
            ("c.png", 155.866),
            ("d.png", 127.891),
        ],
    )
    def test_roll_sign(self, solver, image_name, expected_roll):
        image_bytes = (_SAMPLES_DIR / image_name).read_bytes()
        result = solver.solve_frame(image_bytes)
        assert result["Roll"] is not None
        diff = abs(((result["Roll"] - expected_roll) + 180) % 360 - 180)
        assert diff < 5.0, (
            f"{image_name}: Roll={result['Roll']:.2f}, "
            f"expected {expected_roll:.2f}, |diff|={diff:.2f}° "
            f"— check the (+180) % 360 convention in solver.py"
        )


# ---------------------------------------------------------------------------
# Live-engine sample-injection path (load_sample_jpeg → solve_frame)
# ---------------------------------------------------------------------------


class TestSampleInjectionSolves:
    """Verify each sample still solves after PNG→JPEG re-encode.

    The debug-panel sample-injection path encodes the PNG as JPEG (the
    frame buffer holds JPEG bytes because the real camera produces
    MJPEG). At quality=85 (PIL's default), b.png fell below the
    tetra3rs extractor's centroid threshold while a/c/d/orion still
    solved — only b had no headroom. quality=95 restores the margin.
    This test exercises the actual `load_sample_jpeg` helper so the
    quality value stays gated by the test, not by inspection.
    """

    @pytest.mark.parametrize("name", ["a", "b", "c", "d", "orion"])
    def test_jpeg_encoded_sample_solves(self, solver, name):
        from evf.engine.sample_injector import load_sample_jpeg

        jpeg = load_sample_jpeg(_SAMPLES_DIR, name)
        result = solver.solve_frame(jpeg)
        assert result["RA"] is not None, (
            f"{name}: solve_frame returned no RA after PNG→JPEG re-encode. "
            f"The sample injector quality may have regressed below the "
            f"tetra3rs extractor threshold — see load_sample_jpeg in "
            f"python/evf/engine/sample_injector.py."
        )
        assert result["Matches"] >= 8, (
            f"{name}: only {result['Matches']} matches — insufficient margin "
            f"after PNG→JPEG re-encode."
        )


# ---------------------------------------------------------------------------
# Result validation (§6.3)
# ---------------------------------------------------------------------------


class TestIsValid:
    def test_valid_result(self):
        result = {"RA": 79.0, "Dec": 46.0, "Matches": 10, "Prob": 0.01}
        assert PlateSolver.is_valid(result) is True

    def test_no_solve(self):
        result = {"RA": None}
        assert PlateSolver.is_valid(result) is False

    def test_too_few_matches(self):
        result = {"RA": 79.0, "Dec": 46.0, "Matches": 3, "Prob": 0.01}
        assert PlateSolver.is_valid(result) is False

    def test_probability_too_high(self):
        result = {"RA": 79.0, "Dec": 46.0, "Matches": 10, "Prob": 0.5}
        assert PlateSolver.is_valid(result) is False

    def test_custom_thresholds(self):
        result = {"RA": 79.0, "Dec": 46.0, "Matches": 50, "Prob": 0.001}
        assert PlateSolver.is_valid(result, min_matches=100) is False
        assert PlateSolver.is_valid(result, min_matches=50, max_prob=0.01) is True


# ---------------------------------------------------------------------------
# Solver thread integration (§6.4 verification)
# ---------------------------------------------------------------------------


class TestSolverThread:
    def test_solve_and_update_pointing(self, solver, tmp_path):
        """Inject a sample frame — PointingState updated, state → TRACKING."""
        fb = LatestFrame()
        ps = PointingState()
        sm = StateMachine()
        cfg = ConfigManager(config_dir=tmp_path)

        st = SolverThread(solver, fb, ps, sm, cfg)

        # Inject sample b.png (easiest to solve)
        image_bytes = (_SAMPLES_DIR / "b.png").read_bytes()
        fb.set(image_bytes, time.monotonic(), 1)

        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        st.start()
        assert sm.state == EngineState.WARMING_UP

        # Wait for solve to complete
        deadline = time.monotonic() + 15.0
        while sm.state != EngineState.TRACKING and time.monotonic() < deadline:
            time.sleep(0.1)

        st.stop()

        assert sm.state == EngineState.TRACKING
        snap = ps.read()
        assert snap.valid
        assert abs(snap.ra_j2000 - 132.88) < 2
        assert abs(snap.dec_j2000 - 46.37) < 2

    def test_blank_image_no_update(self, solver, tmp_path):
        """Blank image should not update PointingState."""
        fb = LatestFrame()
        ps = PointingState()
        sm = StateMachine()
        cfg = ConfigManager(config_dir=tmp_path)

        st = SolverThread(solver, fb, ps, sm, cfg)

        # Create a blank black JPEG
        blank = Image.new("L", (1280, 720), 0)
        buf = io.BytesIO()
        blank.save(buf, format="JPEG")
        fb.set(buf.getvalue(), time.monotonic(), 1)

        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        st.start()
        time.sleep(3.0)  # give solver time to attempt
        st.stop()

        assert sm.state == EngineState.WARMING_UP  # never reached TRACKING
        snap = ps.read()
        assert not snap.valid
        assert st.consecutive_failures >= 1

    def test_strict_threshold_rejects_all(self, solver, tmp_path):
        """With min_matches=100, all solves should be rejected."""
        fb = LatestFrame()
        ps = PointingState()
        sm = StateMachine()
        cfg = ConfigManager(config_dir=tmp_path)
        cfg.min_matches = 100  # unreachably high

        st = SolverThread(solver, fb, ps, sm, cfg)

        image_bytes = (_SAMPLES_DIR / "b.png").read_bytes()
        fb.set(image_bytes, time.monotonic(), 1)

        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        st.start()
        time.sleep(3.0)
        st.stop()

        assert sm.state == EngineState.WARMING_UP  # never reached TRACKING
        snap = ps.read()
        assert not snap.valid
        assert st.consecutive_failures >= 1
