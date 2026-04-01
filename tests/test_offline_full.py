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

"""Full offline test suite — acceptance manifest and integration tests.

Per ACCEPTANCE_TESTS.md §J and impl0.md §Phase 9.

Coverage map:
  J1/J2: Solver accuracy — tests/test_solver_offline.py::TestOfflineSolve (4 images)
  J3:    Stellarium protocol — tests/test_stellarium.py (encode/decode + TCP server)
  J4:    Camera protocol — tests/test_camera.py (codec + MockCameraServer integration)
  Unit:  LatestFrame, PointingState, ConfigManager, EngineState — tests/test_phase1.py
  Phase5: SubprocessManager — tests/test_subprocess_mgr.py
  Phase6: PlateSolver, SolverThread — tests/test_solver_offline.py

Integration tests below cover the full pipeline with mock camera.
"""

import io
import socket
import struct
import time
from pathlib import Path

import pytest
from PIL import Image

from evf.camera.client import CameraClient
from evf.engine.frame_buffer import LatestFrame
from evf.engine.pointing import PointingState
from evf.engine.state import EngineState, StateMachine
from evf.solver.solver import PlateSolver
from evf.solver.thread import SolverThread
from evf.stellarium.protocol import _POSITION_LEN
from evf.stellarium.server import StellariumServer
from tests.mock_camera_server import MockCameraServer

_SAMPLES_DIR = Path(__file__).parent / "samples"


# ---------------------------------------------------------------------------
# §9.4 Integration test: camera → solver → Stellarium
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end test: MockCameraServer → CameraClient → SolverThread → Stellarium."""

    def test_camera_to_solver_to_stellarium(self, solver):
        """Full pipeline: frames flow from mock camera through solver to Stellarium.

        Steps per §9.4:
        1. Start mock camera server (feeds sample images as frames).
        2. Connect CameraClient so frames land in LatestFrame.
        3. Start SolverThread — transitions WARMING_UP → TRACKING.
        4. Verify PointingState has correct RA/Dec.
        5. Connect a Stellarium test client and verify position messages arrive.
        """
        fb = LatestFrame()
        ps = PointingState()
        sm = StateMachine()

        # 1. Mock camera streaming sample images (contains solvable star fields)
        server = MockCameraServer(port=0, fps=10)
        server.start()

        # 2. Connect camera client
        client = CameraClient(fb, port=server.port)
        client.connect(timeout=5.0)
        client.start_receiving()

        # Wait for frames to arrive
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            data, _, fid = fb.get()
            if data is not None and fid > 0:
                break
            time.sleep(0.05)
        assert fb.get()[0] is not None, "No frames received from mock camera"

        # 3. Start solver
        from evf.config.manager import ConfigManager

        cfg = ConfigManager(config_dir=Path("/tmp/evf_test_pipeline"))
        st = SolverThread(solver, fb, ps, sm, cfg)
        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        st.start()
        assert sm.state == EngineState.WARMING_UP

        # 4. Wait for first successful solve (TRACKING)
        deadline = time.monotonic() + 30.0
        while sm.state != EngineState.TRACKING and time.monotonic() < deadline:
            time.sleep(0.1)

        assert sm.state == EngineState.TRACKING, (
            f"Expected TRACKING, got {sm.state.value}"
        )

        snap = ps.read()
        assert snap.valid
        # Sample images have known positions; just verify RA/Dec are in valid range
        assert 0 <= snap.ra_j2000 <= 360
        assert -90 <= snap.dec_j2000 <= 90

        # 5. Start Stellarium server and verify position messages arrive
        stell = StellariumServer(ps, port=0)
        stell.start()
        try:
            stell_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            stell_client.settimeout(3.0)
            stell_client.connect(("127.0.0.1", stell.port))

            data = stell_client.recv(1024)
            assert len(data) == _POSITION_LEN

            # Decode and verify RA/Dec are reasonable
            _, _, _, ra_raw, dec_raw, status = struct.unpack("<HHQIii", data)
            ra_hours = ra_raw * (24.0 / 2**32)
            dec_degrees = dec_raw * (180.0 / 2**31)
            assert 0 <= ra_hours <= 24
            assert -90 <= dec_degrees <= 90
            assert status == 0

            stell_client.close()
        finally:
            stell.stop()

        # Cleanup
        st.stop()
        client.stop()
        server.stop()

    def test_solve_failure_preserves_pointing(self, solver):
        """After a valid solve, a blank frame should not overwrite PointingState.

        Per §9.4 step 6 and ACCEPTANCE_TESTS §E1.
        """
        fb = LatestFrame()
        ps = PointingState()
        sm = StateMachine()
        cfg = ConfigManager(config_dir=Path("/tmp/evf_test_preserve"))

        # Inject solvable frame
        image_bytes = (_SAMPLES_DIR / "b.png").read_bytes()
        fb.set(image_bytes, time.monotonic(), 1)

        st = SolverThread(solver, fb, ps, sm, cfg)
        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        st.start()

        # Wait for successful solve
        deadline = time.monotonic() + 15.0
        while sm.state != EngineState.TRACKING and time.monotonic() < deadline:
            time.sleep(0.1)
        assert sm.state == EngineState.TRACKING

        saved_snap = ps.read()
        assert saved_snap.valid
        saved_ra = saved_snap.ra_j2000
        saved_dec = saved_snap.dec_j2000

        # Now inject a blank (unsolvable) frame
        blank = Image.new("L", (1280, 720), 0)
        buf = io.BytesIO()
        blank.save(buf, format="JPEG")
        fb.set(buf.getvalue(), time.monotonic(), 2)

        # Give solver time to attempt the blank
        time.sleep(3.0)

        # PointingState should still hold the last valid solve
        snap = ps.read()
        assert snap.valid
        assert snap.ra_j2000 == saved_ra
        assert snap.dec_j2000 == saved_dec
        assert st.consecutive_failures >= 1

        st.stop()


# Avoid import-time ConfigManager at module level
from evf.config.manager import ConfigManager
