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

"""Tests for LX200 protocol formatters, parsers, and dispatch."""

import pytest

from evf.lx200 import protocol


class TestFormatRa:
    def test_zero(self):
        assert protocol.format_ra_hi(0.0) == b"00:00:00#"

    def test_known_value(self):
        # 5h 47m 12s = 5 + 47/60 + 12/3600 = 5.7867 h
        assert protocol.format_ra_hi(5.7866666666) == b"05:47:12#"

    def test_wraps_at_24h(self):
        # 24.0 wraps to 00:00:00
        assert protocol.format_ra_hi(24.0) == b"00:00:00#"

    def test_low_precision(self):
        # 5h 47.2m
        assert protocol.format_ra_lo(5.78666666) == b"05:47.2#"


class TestFormatDec:
    def test_zero(self):
        assert protocol.format_dec_hi(0.0) == b"+00*00:00#"

    def test_positive_known(self):
        # +45° 59' 07" = 45 + 59/60 + 7/3600 ≈ 45.9853
        assert protocol.format_dec_hi(45.98527778) == b"+45*59:07#"

    def test_minus_zero(self):
        # Negative numbers with zero degrees: the classic sign-formatting trap
        assert protocol.format_dec_hi(-0.5) == b"-00*30:00#"

    def test_plus_90(self):
        assert protocol.format_dec_hi(90.0) == b"+90*00:00#"

    def test_minus_90(self):
        assert protocol.format_dec_hi(-90.0) == b"-90*00:00#"

    def test_low_precision(self):
        assert protocol.format_dec_lo(45.985) == b"+45*59#"


class TestParseRa:
    def test_hi_precision(self):
        assert abs(protocol.parse_ra_hms("05:47:12") - 5.78666666) < 1e-6

    def test_lo_precision(self):
        assert abs(protocol.parse_ra_hms("05:47.2") - 5.78666666) < 1e-4

    def test_wraps(self):
        # >= 24 wraps
        assert protocol.parse_ra_hms("24:00:00") == 0.0


class TestParseDec:
    def test_positive_hi(self):
        assert abs(protocol.parse_dec_dms("+45*59:07") - 45.98527778) < 1e-6

    def test_negative(self):
        assert abs(protocol.parse_dec_dms("-00*30") - (-0.5)) < 1e-6

    def test_plus_90(self):
        assert protocol.parse_dec_dms("+90*00:00") == 90.0

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            protocol.parse_dec_dms("+91*00:00")
        with pytest.raises(ValueError):
            protocol.parse_dec_dms("-91*00:00")

    def test_accepts_unicode_degree_sign(self):
        # Some clients may send the real degree sign (U+00B0) instead of '*'.
        assert abs(protocol.parse_dec_dms("+45\u00b030:00") - 45.5) < 1e-6


class TestRoundTrip:
    @pytest.mark.parametrize("ra_hours", [0.0, 5.78666666, 12.5, 23.99972])
    def test_ra_hi_round_trip(self, ra_hours: float):
        s = protocol.format_ra_hi(ra_hours).decode().rstrip("#")
        back = protocol.parse_ra_hms(s)
        assert abs(back - ra_hours) < 1.0 / 3600.0  # within 1 arc-second

    @pytest.mark.parametrize("dec_deg", [-89.99, -45.5, -0.5, 0.0, 0.5, 45.5, 89.99])
    def test_dec_hi_round_trip(self, dec_deg: float):
        s = protocol.format_dec_hi(dec_deg).decode().rstrip("#")
        back = protocol.parse_dec_dms(s)
        assert abs(back - dec_deg) < 1.0 / 3600.0  # within 1 arc-second


# -- dispatch tests ----------------------------------------------------------

from unittest.mock import MagicMock

from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.lx200.protocol import Lx200ClientState, Lx200Context, dispatch


def _make_ctx(pointing: PointingState, goto: GotoTarget | None = None,
              version: str = "1.2.3", play_ack=None) -> Lx200Context:
    return Lx200Context(
        pointing=pointing,
        goto_target=goto,
        play_ack=play_ack or MagicMock(),
        app_version=version,
    )


class TestDispatchGetters:
    def test_gr_invalid_pointing_returns_zero(self):
        ps = PointingState()
        state = Lx200ClientState()
        ctx = _make_ctx(ps)
        assert dispatch(b":GR", state, ctx) == b"00:00:00#"

    def test_gd_invalid_pointing_returns_zero(self):
        ps = PointingState()
        state = Lx200ClientState()
        ctx = _make_ctx(ps)
        assert dispatch(b":GD", state, ctx) == b"+00*00:00#"

    def test_gr_valid_pointing_returns_formatted(self):
        ps = PointingState()
        # Vega J2000 (RA in degrees, PointingState convention)
        ps.update(ra_j2000=279.234, dec_j2000=38.784, roll=0.0, matches=10, prob=0.01)
        state = Lx200ClientState()
        ctx = _make_ctx(ps)
        reply = dispatch(b":GR", state, ctx)
        # Should be HH:MM:SS# format; we don't hard-code the JNow-precessed value
        # because it's time-dependent. Just verify shape.
        assert reply is not None
        assert reply.endswith(b"#")
        assert len(reply) == 9  # "HH:MM:SS#"
        assert reply[2:3] == b":"
        assert reply[5:6] == b":"

    def test_gvp_returns_identity(self):
        ps = PointingState()
        state = Lx200ClientState()
        ctx = _make_ctx(ps)
        assert dispatch(b":GVP", state, ctx) == b"LX200 Classic#"

    def test_gvn_returns_version(self):
        ps = PointingState()
        state = Lx200ClientState()
        ctx = _make_ctx(ps, version="1.2.3")
        assert dispatch(b":GVN", state, ctx) == b"PushNav 1.2.3#"

    def test_precision_toggle(self):
        ps = PointingState()
        ps.update(ra_j2000=90.0, dec_j2000=45.0, roll=0.0, matches=10, prob=0.01)
        state = Lx200ClientState()
        ctx = _make_ctx(ps)
        # Default is high precision
        assert state.precision_hi is True
        r1 = dispatch(b":GR", state, ctx)
        assert len(r1) == 9  # HH:MM:SS#
        # Toggle
        assert dispatch(b":U", state, ctx) is None
        assert state.precision_hi is False
        r2 = dispatch(b":GR", state, ctx)
        # Low precision: HH:MM.T#  (8 chars)
        assert len(r2) == 8


class TestDispatchSetters:
    """Pending target lives on the Lx200Context (shared across all client
    connections of a server) — SkySafari's polling mode sends :Sr, :Sd, :MS
    on three separate TCP connections, so the pending state must survive
    reconnects. Tests therefore check ctx.pending_*, not state.pending_*.
    """

    def test_sr_valid(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b":Sr 05:47:12", state, ctx) == b"1"
        assert ctx.pending_ra_jnow_hours is not None
        assert abs(ctx.pending_ra_jnow_hours - 5.78666666) < 1e-4

    def test_sd_valid(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b":Sd +45*59:07", state, ctx) == b"1"
        assert ctx.pending_dec_jnow_deg is not None
        assert abs(ctx.pending_dec_jnow_deg - 45.9853) < 1e-3

    def test_sr_malformed(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b":Sr BAD", state, ctx) == b"0"
        assert ctx.pending_ra_jnow_hours is None

    def test_sd_out_of_range(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b":Sd +91*00:00", state, ctx) == b"0"

    def test_sr_sd_ms_across_separate_client_states(self):
        """Regression test for SkySafari polling mode: :Sr, :Sd, :MS arrive
        on three different TCP connections (each with its own fresh
        Lx200ClientState), but they share the same Lx200Context and so the
        pending target accumulates correctly."""
        goto = GotoTarget()
        ctx = _make_ctx(PointingState(), goto=goto)
        state_a = Lx200ClientState()
        state_b = Lx200ClientState()
        state_c = Lx200ClientState()
        assert dispatch(b":Sr 12:00:00", state_a, ctx) == b"1"
        assert dispatch(b":Sd +00*00:00", state_b, ctx) == b"1"
        assert dispatch(b":MS", state_c, ctx) == b"0"
        assert goto.read().active is True


class TestDispatchGoto:
    def test_ms_with_pending_sets_goto(self):
        goto = GotoTarget()
        ps = PointingState()
        ack = MagicMock()
        ctx = _make_ctx(ps, goto=goto, play_ack=ack)
        state = Lx200ClientState()
        dispatch(b":Sr 12:00:00", state, ctx)
        dispatch(b":Sd +00*00:00", state, ctx)
        reply = dispatch(b":MS", state, ctx)
        assert reply == b"0"
        snap = goto.read()
        assert snap.active is True
        # :Sr 12:00:00 JNow = 180° JNow RA. Precessed back to J2000 should be
        # close to 180° (within ~0.5° for 2026 era).
        assert abs(snap.ra_j2000 - 180.0) < 2.0
        # NOTE: goto_target.set() plays the ack sound internally. Our play_ack
        # callable should NOT be invoked by dispatch (to avoid double-play).
        ack.assert_not_called()

    def test_ms_without_pending_returns_error(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState(), goto=GotoTarget())
        assert dispatch(b":MS", state, ctx) == b"1<no target set>#"


class TestDispatchDistance:
    """`:D#` tells SkySafari whether the scope has finished slewing; it uses
    the reply to transition the button from "Stop" back to "GoTo" after a
    goto.  For a push-to, "slew complete" means the plate-solve is within
    _SLEW_DONE_THRESHOLD_DEG of the committed target."""

    def test_d_no_goto_target_reports_done(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState(), goto=GotoTarget())
        assert dispatch(b":D", state, ctx) == b"#"

    def test_d_target_active_but_no_valid_pointing_reports_done(self):
        # Avoid "forever slewing" UX when we haven't locked yet.
        goto = GotoTarget()
        goto.set(ra_j2000_deg=100.0, dec_j2000_deg=20.0)
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState(), goto=goto)
        assert dispatch(b":D", state, ctx) == b"#"

    def test_d_pointing_far_from_target_reports_slewing(self):
        goto = GotoTarget()
        goto.set(ra_j2000_deg=100.0, dec_j2000_deg=20.0)
        ps = PointingState()
        ps.update(ra_j2000=150.0, dec_j2000=30.0, roll=0.0, matches=10, prob=0.01)
        state = Lx200ClientState()
        ctx = _make_ctx(ps, goto=goto)
        assert dispatch(b":D", state, ctx) == b"\x7f#"

    def test_d_pointing_on_target_reports_done(self):
        goto = GotoTarget()
        goto.set(ra_j2000_deg=100.0, dec_j2000_deg=20.0)
        ps = PointingState()
        # 0.1° off in each axis -> ~0.14° separation, well under the 0.5° threshold
        ps.update(ra_j2000=100.1, dec_j2000=20.1, roll=0.0, matches=10, prob=0.01)
        state = Lx200ClientState()
        ctx = _make_ctx(ps, goto=goto)
        assert dispatch(b":D", state, ctx) == b"#"


class TestDispatchCm:
    """Per the one-way data flow rule, :CM# is acknowledge-only."""

    def test_cm_returns_canonical_string(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        reply = dispatch(b":CM", state, ctx)
        assert reply == b"Coordinates matched.        #"

    def test_cm_does_not_mutate_state(self):
        goto = GotoTarget()
        goto.set(ra_j2000_deg=10.0, dec_j2000_deg=20.0)
        snap_before = goto.read()
        state = Lx200ClientState()
        dispatch(b":Sr 05:00:00", state, ctx := _make_ctx(PointingState(), goto=goto))
        dispatch(b":Sd +45*00:00", state, ctx)
        dispatch(b":CM", state, ctx)
        snap_after = goto.read()
        # goto_target must be UNCHANGED — :CM# never mutates
        assert snap_before.ra_j2000 == snap_after.ra_j2000
        assert snap_before.dec_j2000 == snap_after.dec_j2000


class TestDispatchMisc:
    def test_q_clears_pending(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        ctx.pending_ra_jnow_hours = 5.0
        ctx.pending_dec_jnow_deg = 45.0
        assert dispatch(b":Q", state, ctx) is None
        assert ctx.pending_ra_jnow_hours is None
        assert ctx.pending_dec_jnow_deg is None

    def test_unknown_command_returns_none(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b":ED", state, ctx) is None
        assert dispatch(b":$BDG", state, ctx) is None

    def test_malformed_no_colon_returns_none(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b"GR", state, ctx) is None

    def test_empty_returns_none(self):
        state = Lx200ClientState()
        ctx = _make_ctx(PointingState())
        assert dispatch(b"", state, ctx) is None
