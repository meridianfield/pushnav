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
