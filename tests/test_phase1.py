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

"""Unit tests for Phase 1 — core data structures, config, and logging."""

import json
import logging
import threading
import time

import pytest

from evf.engine.state import EngineState, InvalidTransitionError, StateMachine
from evf.engine.frame_buffer import LatestFrame
from evf.engine.pointing import PointingState
from evf.config.manager import ConfigManager, CONFIG_VERSION, DEFAULT_CONFIG
from evf.config.logging_setup import setup_logging


# ---------------------------------------------------------------------------
# EngineState
# ---------------------------------------------------------------------------

class TestEngineState:
    def test_initial_state(self):
        sm = StateMachine()
        assert sm.state is EngineState.SETUP

    def test_valid_transitions(self):
        cases = [
            (EngineState.SETUP, EngineState.SYNC),
            (EngineState.SYNC, EngineState.SYNC_CONFIRM),
            (EngineState.SYNC, EngineState.SETUP),
            (EngineState.SYNC, EngineState.RECONNECTING),
            (EngineState.SYNC_CONFIRM, EngineState.WARMING_UP),
            (EngineState.SYNC_CONFIRM, EngineState.SYNC),
            (EngineState.SYNC_CONFIRM, EngineState.SETUP),
            (EngineState.SYNC_CONFIRM, EngineState.RECONNECTING),
            (EngineState.WARMING_UP, EngineState.TRACKING),
            (EngineState.TRACKING, EngineState.SETUP),
            (EngineState.SETUP, EngineState.RECONNECTING),
            (EngineState.WARMING_UP, EngineState.RECONNECTING),
            (EngineState.TRACKING, EngineState.RECONNECTING),
            (EngineState.RECONNECTING, EngineState.SETUP),
            (EngineState.RECONNECTING, EngineState.ERROR),
            (EngineState.ERROR, EngineState.SETUP),
        ]
        for from_state, to_state in cases:
            sm = StateMachine()
            # Navigate to from_state first
            sm._state = from_state
            sm.transition(to_state)
            assert sm.state is to_state

    def test_invalid_transitions(self):
        invalid = [
            (EngineState.SETUP, EngineState.WARMING_UP),
            (EngineState.SETUP, EngineState.TRACKING),
            (EngineState.SETUP, EngineState.ERROR),
            (EngineState.TRACKING, EngineState.WARMING_UP),
            (EngineState.TRACKING, EngineState.ERROR),
            (EngineState.ERROR, EngineState.TRACKING),
            (EngineState.ERROR, EngineState.RECONNECTING),
        ]
        for from_state, to_state in invalid:
            sm = StateMachine()
            sm._state = from_state
            with pytest.raises(InvalidTransitionError):
                sm.transition(to_state)

    def test_warming_up_to_setup(self):
        """Tracking can be disabled from WARMING_UP (back to SETUP)."""
        sm = StateMachine()
        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        sm.transition(EngineState.WARMING_UP)
        sm.transition(EngineState.SETUP)
        assert sm.state is EngineState.SETUP

    def test_full_tracking_lifecycle(self):
        sm = StateMachine()
        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        sm.transition(EngineState.WARMING_UP)
        sm.transition(EngineState.TRACKING)
        sm.transition(EngineState.SETUP)
        assert sm.state is EngineState.SETUP

    def test_reconnection_cycle(self):
        sm = StateMachine()
        sm.transition(EngineState.SYNC)
        sm.transition(EngineState.SYNC_CONFIRM)
        sm.transition(EngineState.WARMING_UP)
        sm.transition(EngineState.RECONNECTING)
        sm.transition(EngineState.SETUP)
        assert sm.state is EngineState.SETUP

    def test_reconnection_to_error(self):
        sm = StateMachine()
        sm.transition(EngineState.RECONNECTING)
        sm.transition(EngineState.ERROR)
        sm.transition(EngineState.SETUP)
        assert sm.state is EngineState.SETUP

    def test_allowed_transitions_returns_copy(self):
        allowed = StateMachine.allowed_transitions(EngineState.SETUP)
        assert EngineState.SYNC in allowed
        allowed.clear()
        # Original unchanged
        assert EngineState.SYNC in StateMachine.allowed_transitions(EngineState.SETUP)


# ---------------------------------------------------------------------------
# LatestFrame
# ---------------------------------------------------------------------------

class TestLatestFrame:
    def test_empty(self):
        buf = LatestFrame()
        data, ts, fid = buf.get()
        assert data is None
        assert ts == 0.0
        assert fid == 0

    def test_set_and_get(self):
        buf = LatestFrame()
        buf.set(b"jpeg1", 1.0, 1)
        data, ts, fid = buf.get()
        assert data == b"jpeg1"
        assert ts == 1.0
        assert fid == 1

    def test_overwrite(self):
        buf = LatestFrame()
        buf.set(b"jpeg1", 1.0, 1)
        buf.set(b"jpeg2", 2.0, 2)
        data, ts, fid = buf.get()
        assert data == b"jpeg2"
        assert ts == 2.0
        assert fid == 2

    def test_clear(self):
        buf = LatestFrame()
        buf.set(b"jpeg1", 1.0, 1)
        buf.clear()
        data, _, _ = buf.get()
        assert data is None

    def test_thread_safety(self):
        """Smoke test: concurrent set/get should not crash."""
        buf = LatestFrame()
        errors = []

        def writer():
            try:
                for i in range(1000):
                    buf.set(f"frame{i}".encode(), float(i), i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(1000):
                    buf.get()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# PointingState
# ---------------------------------------------------------------------------

class TestPointingState:
    def test_initial_invalid(self):
        ps = PointingState()
        snap = ps.read()
        assert snap.valid is False
        assert snap.ra_j2000 == 0.0

    def test_update_and_read(self):
        ps = PointingState()
        ps.update(ra_j2000=12.5, dec_j2000=45.0, roll=1.2, matches=15, prob=0.05)
        snap = ps.read()
        assert snap.valid is True
        assert snap.ra_j2000 == 12.5
        assert snap.dec_j2000 == 45.0
        assert snap.roll == 1.2
        assert snap.matches == 15
        assert snap.prob == 0.05
        assert snap.last_success_timestamp > 0

    def test_invalidate(self):
        ps = PointingState()
        ps.update(ra_j2000=10.0, dec_j2000=20.0, roll=0.0, matches=10, prob=0.1)
        ps.invalidate()
        snap = ps.read()
        assert snap.valid is False
        # RA/Dec preserved even though invalid
        assert snap.ra_j2000 == 10.0

    def test_snapshot_is_immutable(self):
        ps = PointingState()
        ps.update(ra_j2000=10.0, dec_j2000=20.0, roll=0.0, matches=10, prob=0.1)
        snap = ps.read()
        # Frozen dataclass — cannot modify
        with pytest.raises(AttributeError):
            snap.ra_j2000 = 999.0

    def test_thread_safety(self):
        ps = PointingState()
        errors = []

        def writer():
            try:
                for i in range(500):
                    ps.update(float(i), float(i), 0.0, i, 0.01)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(500):
                    ps.read()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class TestConfigManager:
    def test_creates_default(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert (tmp_path / "config.json").exists()
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["version"] == CONFIG_VERSION
        assert data["solver"]["min_matches"] == 8

    def test_loads_existing(self, tmp_path):
        cfg = {
            "version": CONFIG_VERSION,
            "solver": {"min_matches": 12, "max_prob": 0.3},
            "camera": {"exposure": 200, "gain": 20},
            "logging": {"verbose": True},
        }
        (tmp_path / "config.json").write_text(json.dumps(cfg))
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.min_matches == 12
        assert cm.max_prob == 0.3
        assert cm.exposure == 200
        assert cm.gain == 20
        assert cm.verbose is True

    def test_saves_changes(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.min_matches = 15
        # Reload from disk
        cm2 = ConfigManager(config_dir=tmp_path)
        assert cm2.min_matches == 15

    def test_version_mismatch_resets(self, tmp_path):
        cfg = {"version": 999, "solver": {"min_matches": 50}}
        (tmp_path / "config.json").write_text(json.dumps(cfg))
        cm = ConfigManager(config_dir=tmp_path)
        # Should have reset to defaults
        assert cm.min_matches == DEFAULT_CONFIG["solver"]["min_matches"]

    def test_corrupt_json_resets(self, tmp_path):
        (tmp_path / "config.json").write_text("NOT JSON{{{")
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.min_matches == DEFAULT_CONFIG["solver"]["min_matches"]

    def test_merges_missing_keys(self, tmp_path):
        """If config is missing a section, defaults are merged in."""
        cfg = {"version": CONFIG_VERSION, "solver": {"min_matches": 10, "max_prob": 0.1}}
        (tmp_path / "config.json").write_text(json.dumps(cfg))
        cm = ConfigManager(config_dir=tmp_path)
        # Existing values preserved
        assert cm.min_matches == 10
        # Missing sections filled with defaults
        assert cm.exposure == DEFAULT_CONFIG["camera"]["exposure"]

    def test_path_property(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.path == tmp_path / "config.json"

    def test_data_returns_copy(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        d = cm.data
        d["solver"]["min_matches"] = 999
        assert cm.min_matches == DEFAULT_CONFIG["solver"]["min_matches"]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

class TestLogging:
    def test_log_file_created(self, tmp_path):
        setup_logging(verbose=False, console=False, log_dir=tmp_path)
        logger = logging.getLogger("test_logging")
        logger.info("test message")
        # Flush
        for h in logging.getLogger().handlers:
            h.flush()
        log_file = tmp_path / "evf.log"
        assert log_file.exists()
        contents = log_file.read_text()
        assert "test message" in contents

    def test_verbose_enables_debug(self, tmp_path):
        setup_logging(verbose=True, console=False, log_dir=tmp_path)
        logger = logging.getLogger("test_verbose")
        logger.debug("debug msg")
        for h in logging.getLogger().handlers:
            h.flush()
        contents = (tmp_path / "evf.log").read_text()
        assert "debug msg" in contents

    def test_non_verbose_filters_debug(self, tmp_path):
        setup_logging(verbose=False, console=False, log_dir=tmp_path)
        logger = logging.getLogger("test_nonverbose")
        logger.debug("secret debug")
        for h in logging.getLogger().handlers:
            h.flush()
        contents = (tmp_path / "evf.log").read_text()
        assert "secret debug" not in contents

    def test_rotation(self, tmp_path):
        """Write enough to trigger at least one rotation."""
        setup_logging(verbose=False, console=False, log_dir=tmp_path)
        logger = logging.getLogger("test_rotation")
        # Write ~6 MB to exceed 5 MB limit
        msg = "X" * 1000
        for _ in range(6500):
            logger.info(msg)
        for h in logging.getLogger().handlers:
            h.flush()
        log_files = list(tmp_path.glob("evf.log*"))
        assert len(log_files) >= 2, f"Expected rotation, got files: {log_files}"
