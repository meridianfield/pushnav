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

"""Trim vendored OpenNGC + HYG CSVs into the JSON projections that
the React UI imports.

Run from the repo root:

    uv run python scripts/build_catalogs.py

The script is idempotent and gated on source-CSV mtimes inside
scripts/run_dev*, so dev workflows don't pay the trim cost on every
launch.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENNGC_CSV = REPO_ROOT / "data" / "catalogs" / "openngc" / "NGC.csv"
HYG_CSV     = REPO_ROOT / "data" / "catalogs" / "hyg"     / "hygdata_v3.csv"
OPENNGC_OUT = REPO_ROOT / "web" / "src" / "data" / "openngc.json"
HYG_OUT     = REPO_ROOT / "web" / "src" / "data" / "hyg-bright.json"


# ----- shared helpers --------------------------------------------------------

def _hms_to_deg(s: str) -> float:
    """'HH:MM:SS.s' → decimal degrees of arc on the equator (×15 from hours)."""
    h, m, sec = s.strip().split(":")
    return (float(h) + float(m) / 60 + float(sec) / 3600) * 15


def _dms_to_deg(s: str) -> float:
    """'±DD:MM:SS.s' → decimal degrees."""
    s = s.strip()
    sign = -1 if s.startswith("-") else 1
    if s[0] in "+-":
        s = s[1:]
    d, m, sec = s.split(":")
    return sign * (float(d) + float(m) / 60 + float(sec) / 3600)


_GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε",
    "Zet": "ζ", "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ",
    "Lam": "λ", "Mu":  "μ", "Nu":  "ν", "Xi":  "ξ", "Omi": "ο",
    "Pi":  "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ",
    "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}


def _bayer_flam_pretty(bf: str) -> tuple[str | None, str | None]:
    """HYG's `bf` field encodes Flamsteed + Bayer in one string:

        "9Alp CMa"   → flam="9 CMa", bayer="α CMa"
        "15Bet Cyg"  → flam="15 Cyg", bayer="β Cyg"
        "21Alp Cyg"  → flam="21 Cyg", bayer="α Cyg"
        "53Alp Aql"  → flam="53 Aql", bayer="α Aql"

    The leading digits are the Flamsteed number; the 3-letter Greek
    abbreviation is the Bayer letter; the trailing 3-letter token is
    the IAU constellation abbreviation.

    Returns (flam_label, bayer_label), either of which may be None if
    the corresponding piece is absent.
    """
    bf = bf.strip()
    if not bf:
        return None, None
    m = re.match(r"^\s*(\d+)?\s*([A-Z][a-z]{2})?\s*([A-Z][A-Za-z]{2})\s*$", bf)
    if not m:
        return None, None
    flam_num, bayer_abbr, con = m.groups()
    flam = f"{flam_num} {con}" if flam_num else None
    bayer = f"{_GREEK[bayer_abbr]} {con}" if bayer_abbr and bayer_abbr in _GREEK else None
    return flam, bayer


# ----- OpenNGC --------------------------------------------------------------

def _format_ngc_id(raw: str) -> str:
    """'NGC0224' / 'IC1396'  →  'NGC 224' / 'IC 1396'.

    Falls back to the raw token (with a single space inserted between
    the alphabetic prefix and the trailing number) for anything that
    doesn't start with NGC/IC.
    """
    m = re.match(r"^\s*([A-Za-z]+)\s*0*(\d+)\s*$", raw)
    if not m:
        return raw.strip()
    return f"{m.group(1).upper()} {m.group(2)}"


def _parse_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _split_comma(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def trim_openngc(csv_path: Path) -> list[dict]:
    out: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            kind = (row.get("Type") or "").strip()
            if kind in {"Dup", "*", ""}:
                continue
            ra_raw = (row.get("RA") or "").strip()
            dec_raw = (row.get("Dec") or "").strip()
            if not ra_raw or not dec_raw:
                continue
            ra_deg = _hms_to_deg(ra_raw)
            dec_deg = _dms_to_deg(dec_raw)
            v_mag = _parse_float(row.get("V-Mag", ""))
            b_mag = _parse_float(row.get("B-Mag", ""))
            mag = v_mag if v_mag is not None else b_mag
            aliases: list[str] = []
            messier = (row.get("M") or "").strip()
            if messier:
                aliases.append(f"M {int(messier)}")
            for name in _split_comma(row.get("Common names", "")):
                aliases.append(name)
            for ident in _split_comma(row.get("Identifiers", "")):
                aliases.append(ident)
            out.append({
                "id": _format_ngc_id(row.get("Name", "")),
                "aliases": aliases,
                "type": kind,
                "ra_deg": round(ra_deg, 6),
                "dec_deg": round(dec_deg, 6),
                "mag": round(mag, 2) if mag is not None else None,
                "constellation": (row.get("Const") or "").strip() or None,
            })
    return out


# ----- HYG ------------------------------------------------------------------

def trim_hyg(csv_path: Path) -> list[dict]:
    out: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            proper = (row.get("proper") or "").strip()
            bf_raw = (row.get("bf") or "").strip()
            mag = _parse_float(row.get("mag", ""))
            # Trim rule: any of named / Bayer-Flamsteed / bright
            has_bf = bool(bf_raw)
            bright = mag is not None and mag <= 6.0
            if not (proper or has_bf or bright):
                continue
            ra_h = _parse_float(row.get("ra", ""))
            dec_d = _parse_float(row.get("dec", ""))
            if ra_h is None or dec_d is None:
                continue
            hip = (row.get("hip") or "").strip()
            hd  = (row.get("hd")  or "").strip()
            hr  = (row.get("hr")  or "").strip()
            gl  = (row.get("gl")  or "").strip()
            spect = (row.get("spect") or "").strip() or None
            con = (row.get("con") or "").strip() or None
            flam_label, bayer_label = _bayer_flam_pretty(bf_raw)
            # Best human label, in priority order.
            if proper:
                ident = proper
            elif bayer_label:
                ident = bayer_label
            elif flam_label:
                ident = flam_label
            elif hip:
                ident = f"HIP {hip}"
            elif hd:
                ident = f"HD {hd}"
            elif hr:
                ident = f"HR {hr}"
            elif gl:
                ident = f"Gl {gl}"
            else:
                continue                       # nothing to call this row
            if ident == "Sun":
                continue
            aliases: list[str] = []
            if proper:        aliases.append(proper)
            if bayer_label:   aliases.append(bayer_label)
            if flam_label:    aliases.append(flam_label)
            if hip:           aliases.append(f"HIP {hip}")
            if hd:            aliases.append(f"HD {hd}")
            if hr:            aliases.append(f"HR {hr}")
            if gl:            aliases.append(f"Gl {gl}")
            # De-dup while preserving order.
            seen: set[str] = set()
            aliases = [a for a in aliases if not (a in seen or seen.add(a))]
            out.append({
                "id": ident,
                "aliases": aliases,
                "ra_deg": round(ra_h * 15.0, 6),
                "dec_deg": round(dec_d, 6),
                "mag": round(mag, 2) if mag is not None else None,
                "spectral": spect,
                "constellation": con,
            })
    return out


# ----- CLI ------------------------------------------------------------------

def _write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    ngc = trim_openngc(OPENNGC_CSV)
    _write_json(OPENNGC_OUT, ngc)
    print(f"openngc.json: {len(ngc):>6} entries → {OPENNGC_OUT}")
    hyg = trim_hyg(HYG_CSV)
    _write_json(HYG_OUT, hyg)
    print(f"hyg-bright.json: {len(hyg):>4} entries → {HYG_OUT}")


if __name__ == "__main__":
    main()
