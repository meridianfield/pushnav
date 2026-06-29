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

"""Generate data/tetra3rs_gaia.bin — the prebuilt tetra3rs SolverDatabase.

One-shot dev tool. Run this when:
  - first creating the .bin
  - tetra3rs is upgraded to a version with an incompatible .bin format
  - the db parameters below need to change

Db parameters mirror the existing hip8_database.npz settings (decoded
from its props_packed) for matched-FOV comparison parity. See
docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md.

Run:
    uv run --group dev python scripts/build_tetra3rs_catalog.py
"""

from __future__ import annotations

import time
from pathlib import Path

import tetra3rs

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "tetra3rs_gaia.bin"

MIN_FOV_DEG = 7.0
MAX_FOV_DEG = 10.0
STAR_MAX_MAGNITUDE = 8.0
PATTERN_MAX_ERROR = 0.005
VERIFICATION_STARS_PER_FOV = 30
EPOCH_PROPER_MOTION_YEAR = 2026.0


def main() -> int:
    if OUT_PATH.exists():
        print(f"{OUT_PATH.relative_to(REPO_ROOT)} already exists. "
              "Delete it first if you want to regenerate.")
        return 1
    print(f"Generating tetra3rs db (FOV {MIN_FOV_DEG}°..{MAX_FOV_DEG}°, "
          f"mag<={STAR_MAX_MAGNITUDE})...")
    t0 = time.perf_counter()
    db = tetra3rs.SolverDatabase.generate_from_gaia(
        max_fov_deg=MAX_FOV_DEG,
        min_fov_deg=MIN_FOV_DEG,
        star_max_magnitude=STAR_MAX_MAGNITUDE,
        pattern_max_error=PATTERN_MAX_ERROR,
        verification_stars_per_fov=VERIFICATION_STARS_PER_FOV,
        epoch_proper_motion_year=EPOCH_PROPER_MOTION_YEAR,
    )
    elapsed = time.perf_counter() - t0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    db.save_to_file(str(OUT_PATH))
    size_mb = OUT_PATH.stat().st_size / 1_000_000
    print(f"Built in {elapsed:.1f}s ({db.num_stars} stars, "
          f"{db.num_patterns} patterns), wrote "
          f"{OUT_PATH.relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
