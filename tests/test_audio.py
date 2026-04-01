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

"""Tests for AudioAlert transition detection."""

from unittest.mock import patch

from evf.engine.audio import AudioAlert


class TestAudioAlert:
    """Test failure-count transition detection and sound triggers."""

    def test_zero_to_nonzero_plays_lost(self):
        """0 → 1 should trigger lost sound."""
        alert = AudioAlert(enabled=True)
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(1)
        mock_play.assert_called_once()
        assert "lost" in mock_play.call_args[0][0].name

    def test_nonzero_to_zero_plays_lock(self):
        """3 → 0 should trigger lock sound."""
        alert = AudioAlert(enabled=True)
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(1)  # 0 → 1
            alert.on_failure_count_changed(2)  # 1 → 2
            alert.on_failure_count_changed(3)  # 2 → 3
            mock_play.reset_mock()
            alert.on_failure_count_changed(0)  # 3 → 0
        mock_play.assert_called_once()
        assert "lock" in mock_play.call_args[0][0].name

    def test_nonzero_to_nonzero_no_sound(self):
        """1 → 2 should trigger nothing (still lost)."""
        alert = AudioAlert(enabled=True)
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(1)  # 0 → 1 (triggers lost)
            mock_play.reset_mock()
            alert.on_failure_count_changed(2)  # 1 → 2
        mock_play.assert_not_called()

    def test_zero_to_zero_no_sound(self):
        """0 → 0 should trigger nothing (still locked)."""
        alert = AudioAlert(enabled=True)
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(0)
        mock_play.assert_not_called()

    def test_disabled_no_sound(self):
        """When disabled, no sound should play on any transition."""
        alert = AudioAlert(enabled=False)
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(1)  # 0 → 1
            alert.on_failure_count_changed(0)  # 1 → 0
        mock_play.assert_not_called()

    def test_reset_clears_prev_count(self):
        """reset() should clear prev count so next failure triggers lost."""
        alert = AudioAlert(enabled=True)
        with patch.object(AudioAlert, "_play"):
            alert.on_failure_count_changed(3)  # 0 → 3
        alert.reset()  # clears to 0
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(1)  # 0 → 1 again
        mock_play.assert_called_once()
        assert "lost" in mock_play.call_args[0][0].name

    def test_enabled_toggle_at_runtime(self):
        """Toggling enabled at runtime should take effect immediately."""
        alert = AudioAlert(enabled=True)
        assert alert.enabled is True
        alert.enabled = False
        assert alert.enabled is False
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(1)
        mock_play.assert_not_called()

        # Re-enable and check that transition still tracked
        alert.enabled = True
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(0)  # 1 → 0
        mock_play.assert_called_once()
        assert "lock" in mock_play.call_args[0][0].name

    def test_disabled_still_tracks_state(self):
        """Even when disabled, internal state should update for when re-enabled."""
        alert = AudioAlert(enabled=False)
        alert.on_failure_count_changed(3)  # 0 → 3, no sound
        alert.enabled = True
        with patch.object(AudioAlert, "_play") as mock_play:
            alert.on_failure_count_changed(0)  # 3 → 0, should play lock
        mock_play.assert_called_once()
        assert "lock" in mock_play.call_args[0][0].name
