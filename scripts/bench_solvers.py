#!/usr/bin/env python3
"""tetra3rs quality + perf regression harness.

Solves each frame in tests/samples/ with tetra3rs and prints timing
and solution quality.  Use this to verify all sample frames still solve
after solver or catalog changes, and to measure wall-time performance on
different hardware (laptop, Pi 4, Pi Zero 2 W).

Run (after `uv sync`):

    uv run python scripts/bench_solvers.py

Baseline numbers and historical findings live in:
  specs/start/SPEC_SOLVER_PERFORMANCE.md
  docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md

The script loads the production catalog at data/tetra3rs_gaia.bin.
If that file is missing (unlikely outside the repo), it falls back to
.cache/tetra3rs_gaia.bin, regenerating it from the bundled gaia-catalog
package if needed (~30 s, one-time).
"""

from __future__ import annotations

import math
import platform
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "tests" / "samples"
CACHE_DIR = REPO_ROOT / ".cache"
PROD_DB_PATH = REPO_ROOT / "data" / "tetra3rs_gaia.bin"
CACHE_DB_PATH = CACHE_DIR / "tetra3rs_gaia.bin"

# Match the production solve params from evf.solver.solver.
FOV_DEG = 8.86
FOV_MAX_ERROR_DEG = 1.5

# Match the FOV range / mag cut of the existing tetra3 hip8 database
# (decoded from data/hip8_database.npz props_packed). Same min_fov,
# max_fov, star_max_magnitude, pattern_max_error, and
# verification_stars_per_fov so the solver sees a comparable star set.
# tetra3rs's bundled catalog is Gaia DR3 + Hipparcos (vs Hipparcos-only
# in the legacy hip8 db), so the .bin won't be byte-equivalent — but the
# matchable-star density at our FOV is similar.
DB_MIN_FOV_DEG = 7.0
DB_MAX_FOV_DEG = 10.0
DB_STAR_MAX_MAG = 8.0
DB_PATTERN_MAX_ERROR = 0.005
DB_VERIFY_STARS_PER_FOV = 30

SAMPLES = ["a.png", "b.png", "c.png", "d.png", "orion.png"]


_t3rs_db = None


def get_or_build_t3rs_db():
    import tetra3rs

    # Prefer the production prebuilt so we measure exactly what ships.
    if PROD_DB_PATH.exists():
        print(f"[tetra3rs] loading production db from {PROD_DB_PATH.relative_to(REPO_ROOT)}")
        return tetra3rs.SolverDatabase.load_from_file(str(PROD_DB_PATH))

    # Fall back to cached regen (or generate fresh if needed).
    if CACHE_DB_PATH.exists():
        print(f"[tetra3rs] production db missing; loading cache from {CACHE_DB_PATH.relative_to(REPO_ROOT)}")
        return tetra3rs.SolverDatabase.load_from_file(str(CACHE_DB_PATH))

    print(
        f"[tetra3rs] generating database (FOV {DB_MIN_FOV_DEG}°..{DB_MAX_FOV_DEG}°) "
        "from bundled gaia-catalog — one-time, ~30 s..."
    )
    CACHE_DIR.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    db = tetra3rs.SolverDatabase.generate_from_gaia(
        max_fov_deg=DB_MAX_FOV_DEG,
        min_fov_deg=DB_MIN_FOV_DEG,
        star_max_magnitude=DB_STAR_MAX_MAG,
        pattern_max_error=DB_PATTERN_MAX_ERROR,
        verification_stars_per_fov=DB_VERIFY_STARS_PER_FOV,
        epoch_proper_motion_year=2026.0,
    )
    db.save_to_file(str(CACHE_DB_PATH))
    print(
        f"[tetra3rs] built in {time.perf_counter() - t0:.1f}s "
        f"({db.num_stars} stars, {db.num_patterns} patterns) → "
        f"{CACHE_DB_PATH.relative_to(REPO_ROOT)}"
    )
    return db


def solve_with_tetra3rs(path: Path) -> dict:
    import numpy as np
    import tetra3rs
    from PIL import Image

    global _t3rs_db
    if _t3rs_db is None:
        _t3rs_db = get_or_build_t3rs_db()

    img = Image.open(path).convert("L")
    arr = np.asarray(img, dtype=np.float64)

    # Mirror tetra3's get_centroids_from_image filters as closely as the
    # tetra3rs API allows:
    #   tetra3 sigma=2 (Gaussian-blur on raw image)  → tetra3rs
    #     matched_filter_sigma=2.0 (Gaussian matched filter; suppresses
    #     extended emission like M42 nebulosity vs star-PSF responses).
    #   tetra3 max_area=2000  → tetra3rs max_pixels=2000 (blob-size cap;
    #     belt-and-braces vs extended sources).
    #   tetra3 pattern_checking_stars=30  → tetra3rs max_centroids=30
    #     (brightest-N cap; keeps the matcher's input clean).
    t0 = time.perf_counter()
    extraction = tetra3rs.extract_centroids(
        arr,
        sigma_threshold=5.0,
        max_pixels=2000,
        max_centroids=30,
        matched_filter_sigma=2.0,
    )
    t_extract_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    result = _t3rs_db.solve_from_centroids(
        extraction.centroids,
        fov_estimate_deg=FOV_DEG,
        fov_max_error_deg=FOV_MAX_ERROR_DEG,
        image_shape=arr.shape,
    )
    t_solve_ms = (time.perf_counter() - t0) * 1000

    if result is None:
        return {
            "ok": False,
            "ra": None, "dec": None, "roll": None,
            "matches": 0, "prob": None, "rmse_arcsec": None,
            "status": "no-result",
            "n_centroids": len(extraction.centroids),
            "ms_extract": t_extract_ms,
            "ms_solve": t_solve_ms,
            "ms_wall": t_extract_ms + t_solve_ms,
            "ms_internal": None,
        }

    ok = result.ra_deg is not None and "match_found" in str(result.status).lower()
    return {
        "ok": ok,
        "ra": result.ra_deg,
        "dec": result.dec_deg,
        "roll": result.roll_deg,
        "matches": result.num_matches or 0,
        "prob": result.probability,
        "rmse_arcsec": result.rmse_arcsec,
        "status": str(result.status),
        "n_centroids": len(extraction.centroids),
        "ms_extract": t_extract_ms,
        "ms_solve": t_solve_ms,
        "ms_wall": t_extract_ms + t_solve_ms,
        "ms_internal": result.solve_time_ms,
    }


def main() -> int:
    try:
        import tetra3rs  # noqa: F401
    except ImportError:
        print(
            "tetra3rs not installed. Run `uv sync` then retry:\n"
            "    uv run python scripts/bench_solvers.py",
            file=sys.stderr,
        )
        return 2

    from importlib.metadata import version as _pkg_version

    print(
        f"# bench_solvers.py — {platform.machine()} / "
        f"python {platform.python_version()} / tetra3rs {_pkg_version('tetra3rs')}"
    )
    print()

    cols = "{:<10} {:>12} {:>10} {:>9} {:>8}"
    print(cols.format("sample", "t3rs wall ms", "t3rs int ms", "rmse ″", "matches"))
    print("-" * 55)

    rows = []
    for name in SAMPLES:
        p = SAMPLES_DIR / name
        if not p.exists():
            print(f"{name:<10} (missing)")
            continue
        b = solve_with_tetra3rs(p)

        if not b["ok"]:
            print(
                f"{name:<10} {b['ms_wall']:>12.1f}  "
                f"FAIL ({b.get('status', '?')}, "
                f"matches={b.get('matches')}, centroids={b.get('n_centroids')})"
            )
            continue

        print(
            cols.format(
                name,
                f"{b['ms_wall']:.1f}",
                f"{b['ms_internal']:.1f}",
                f"{b['rmse_arcsec']:.2f}",
                str(b["matches"]),
            )
        )
        rows.append(b)

    if rows:
        print()
        t3rs_avg = sum(r["ms_wall"] for r in rows) / len(rows)
        print(
            f"avg wall: t3rs={t3rs_avg:.1f}ms (n={len(rows)})  "
            f"(baseline laptop ~29 ms, Pi 4 ~215 ms per SPEC_SOLVER_PERFORMANCE.md)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
