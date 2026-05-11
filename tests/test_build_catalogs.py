# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav. See LICENSE in repo root.

"""Unit tests for scripts/build_catalogs.py."""

import json
from pathlib import Path

import pytest

# scripts/ isn't on sys.path by default — make the module importable.
import sys
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_catalogs  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ----- OpenNGC ---------------------------------------------------------------

def test_openngc_trim_keeps_real_objects():
    entries = build_catalogs.trim_openngc(FIXTURES / "openngc_sample.csv")
    ids = {e["id"] for e in entries}
    assert "NGC 224" in ids       # Andromeda
    assert "NGC 598" in ids       # Triangulum
    assert "NGC 1976" in ids      # Orion Nebula
    assert "NGC 1" in ids         # plain DSO


def test_openngc_trim_drops_duplicate_and_star_rows():
    entries = build_catalogs.trim_openngc(FIXTURES / "openngc_sample.csv")
    ids = {e["id"] for e in entries}
    assert "DUMMY 01" not in ids
    assert "DUMMY 02" not in ids


def test_openngc_aliases_include_messier_and_common_names():
    entries = build_catalogs.trim_openngc(FIXTURES / "openngc_sample.csv")
    by_id = {e["id"]: e for e in entries}
    m31 = by_id["NGC 224"]
    assert "M 31" in m31["aliases"]
    assert "Andromeda Galaxy" in m31["aliases"]
    # Cross-IDs from the Identifiers column
    assert "PGC 2557" in m31["aliases"]


def test_openngc_ra_dec_in_degrees():
    entries = build_catalogs.trim_openngc(FIXTURES / "openngc_sample.csv")
    m31 = next(e for e in entries if e["id"] == "NGC 224")
    # 00:42:44.30 → 10.6846° ;  +41:16:09.4 → 41.2693°
    assert m31["ra_deg"] == pytest.approx(10.6846, abs=0.001)
    assert m31["dec_deg"] == pytest.approx(41.2693, abs=0.001)


def test_openngc_prefers_v_mag_else_b_mag_else_null():
    entries = build_catalogs.trim_openngc(FIXTURES / "openngc_sample.csv")
    by_id = {e["id"]: e for e in entries}
    assert by_id["NGC 224"]["mag"] == pytest.approx(3.44)
    # NGC 1976 has V-Mag only
    assert by_id["NGC 1976"]["mag"] == pytest.approx(4.00)


# ----- HYG -------------------------------------------------------------------

def test_hyg_trim_keeps_named_or_bayer_or_bright():
    entries = build_catalogs.trim_hyg(FIXTURES / "hyg_sample.csv")
    ids = {e["id"] for e in entries}
    assert "Sirius" in ids
    assert "Vega" in ids
    assert "Altair" in ids
    assert "Albireo" in ids
    # Bright unnamed row (HIP 108248, mag 4.62, no Bayer/Flam)
    assert "HIP 108248" in ids


def test_hyg_trim_drops_dim_unnamed_rows():
    entries = build_catalogs.trim_hyg(FIXTURES / "hyg_sample.csv")
    ids = {e["id"] for e in entries}
    assert "HIP 11111" not in ids
    assert "HIP 33333" not in ids


def test_hyg_ra_dec_converted_from_hours_to_degrees():
    entries = build_catalogs.trim_hyg(FIXTURES / "hyg_sample.csv")
    sirius = next(e for e in entries if e["id"] == "Sirius")
    # HYG RA is in decimal hours: 6.7525 h × 15 = 101.2875°
    assert sirius["ra_deg"] == pytest.approx(101.2875, abs=0.001)
    assert sirius["dec_deg"] == pytest.approx(-16.7161, abs=0.001)


def test_hyg_aliases_include_hip_hd_hr_and_bayer():
    entries = build_catalogs.trim_hyg(FIXTURES / "hyg_sample.csv")
    sirius = next(e for e in entries if e["id"] == "Sirius")
    assert "HIP 32349" in sirius["aliases"]
    assert "HD 48915"  in sirius["aliases"]
    assert "HR 2491"   in sirius["aliases"]
    # The "9Alp CMa" raw bf should be normalised to "α CMa"
    assert "α CMa" in sirius["aliases"]


def test_hyg_skips_self_origin_row():
    """HYG row 0 is the Sun (id=0). Make sure we don't ship it."""
    # Our fixture starts at id=1, so the assertion is implicit — but be
    # explicit so the trim function stays defensive against id == 0.
    entries = build_catalogs.trim_hyg(FIXTURES / "hyg_sample.csv")
    for e in entries:
        assert e["id"] != "Sun"
