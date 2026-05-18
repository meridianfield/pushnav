#!/usr/bin/env python3
"""Side-by-side bench of tetra3 (Python) vs tetra3rs (Rust).

Solves each frame in tests/samples/ with both solvers and prints
timing + RA/Dec/Roll agreement. No evf runtime code is modified —
this is a read-only sanity check ahead of any wrapper port.

Run on laptop or Pi 4 (after `uv sync`):

    uv run --with tetra3rs --with gaia-catalog --with numpy --with Pillow \\
        python scripts/bench_solvers.py

First run regenerates the tetra3rs Gaia DR3 + Hipparcos database from
the bundled gaia-catalog package and caches it at
.cache/tetra3rs_gaia.bin (~5 MB at our FOV, gitignored).

Findings preserved here (and in
docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md):

  Database params — derived from existing data/hip8_database.npz
  props_packed via the field order in
  python/vendor/tetra3/tetra3/tetra3.py:524-555:
    max_fov_deg=10.0, min_fov_deg=7.0, star_max_magnitude=8.0,
    pattern_max_error=0.005, verification_stars_per_fov=30,
    epoch_proper_motion_year=2026.0
  tetra3rs's bundled catalog is Gaia DR3 + Hipparcos vs Hipparcos-only
  in our hip8 db. At the same FOV/mag cut, tetra3rs's db has ~3× more
  stars (62k vs 21k) but ~11× fewer patterns (1.9M vs 21M) due to
  different pattern enumeration defaults — both solve correctly.

  Centroid extraction params — these took several iterations to land:
    sigma_threshold=5.0 (default; same detection sensitivity)
    max_pixels=2000 (matches tetra3 max_area=2000; blob-size cap)
    max_centroids=30 (matches tetra3 pattern_checking_stars=30; cap)
    matched_filter_sigma=2.0 (CRITICAL — direct analogue of tetra3's
      sigma=2 Gaussian blur). Without it, M42 nebulosity peaks rank
      above real stars in the brightest-30 list, and orion.png fails
      with 0 matches despite being the visually clearest frame.

  API quirks (tetra3rs 0.7.1):
    - solve_from_centroids() returns None on failure (not a SolveResult
      with a failed status).
    - SolveStatus values are lowercase: "match_found" not "MatchFound".
    - num_stars / num_patterns / max_fov_deg / min_fov_deg are PROPERTIES
      on SolverDatabase, not methods.
    - tetra3rs.version is a function, not a string — use
      importlib.metadata.version("tetra3rs").
    - Centroid coordinate convention is image-center origin, +X right,
      +Y down. ExtractionResult.centroids handles this internally; only
      relevant if we ever feed hand-built Centroids to the solver.
    - SolveResult exposes matched_centroids + matched_catalog_ids; the
      catalog star RA/Dec/mag comes via db.get_star_by_id(id). This is
      what evf/solver/sync.py will consume after the port.

  Roll convention:
    tetra3rs roll_deg is ~180° flipped from our currently-negated
    tetra3 Roll (which evf.solver computes as `360 - Roll`). The port
    will need its own one-liner sign handling — different from the
    existing one.

  Baseline (laptop, arm64 M-series, all 5 samples solving, 2026-05-18):
    tetra3 wall: 41–507 ms (median ~150 ms)
    tetra3rs wall: 24–37 ms (extraction dominates)
    tetra3rs internal solve: 0.2–2.1 ms
    Wall speedup: 5.8×; internal speedup: 50–250×
    Max RA/Dec disagreement: 21″ (mean 18″); rmse 10–18″.
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
T3RS_DB_PATH = CACHE_DIR / "tetra3rs_gaia.bin"

# Match the production solve params from evf.solver.solver.
FOV_DEG = 8.86
FOV_MAX_ERROR_DEG = 1.5

# Match the FOV range / mag cut of the existing tetra3 hip8 database
# (decoded from data/hip8_database.npz props_packed). Same min_fov,
# max_fov, star_max_magnitude, pattern_max_error, and
# verification_stars_per_fov so the two solvers see comparable star
# sets. tetra3rs's bundled catalog is Gaia DR3 + Hipparcos (vs
# Hipparcos-only in t3), so the .bin won't be byte-equivalent — but the
# matchable-star density at our FOV is similar.
DB_MIN_FOV_DEG = 7.0
DB_MAX_FOV_DEG = 10.0
DB_STAR_MAX_MAG = 8.0
DB_PATTERN_MAX_ERROR = 0.005
DB_VERIFY_STARS_PER_FOV = 30

SAMPLES = ["a.png", "b.png", "c.png", "d.png", "orion.png"]


_t3_solver = None
_t3rs_db = None


def solve_with_tetra3(path: Path) -> dict:
    """Solve via the production PlateSolver wrapper (vendored tetra3)."""
    global _t3_solver
    if _t3_solver is None:
        sys.path.insert(0, str(REPO_ROOT / "python"))
        from evf.solver.solver import PlateSolver

        _t3_solver = PlateSolver()

    image_bytes = path.read_bytes()
    t0 = time.perf_counter()
    res = _t3_solver.solve_frame(image_bytes)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {
        "ok": res.get("RA") is not None,
        "ra": res.get("RA"),
        "dec": res.get("Dec"),
        "roll": res.get("Roll"),
        "matches": res.get("Matches") or 0,
        "prob": res.get("Prob"),
        "ms_wall": elapsed_ms,
    }


def get_or_build_t3rs_db():
    import tetra3rs

    if T3RS_DB_PATH.exists():
        return tetra3rs.SolverDatabase.load_from_file(str(T3RS_DB_PATH))

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
    db.save_to_file(str(T3RS_DB_PATH))
    print(
        f"[tetra3rs] built in {time.perf_counter() - t0:.1f}s "
        f"({db.num_stars} stars, {db.num_patterns} patterns) → "
        f"{T3RS_DB_PATH.relative_to(REPO_ROOT)}"
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


def angular_separation_arcsec(ra1, dec1, ra2, dec2) -> float:
    if None in (ra1, dec1, ra2, dec2):
        return float("nan")
    phi1, phi2 = math.radians(dec1), math.radians(dec2)
    dphi = math.radians(dec2 - dec1)
    dlam = math.radians(ra2 - ra1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return math.degrees(2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))) * 3600


def wrap_signed_180(d: float) -> float:
    return ((d + 180) % 360) - 180


def main() -> int:
    try:
        import tetra3rs  # noqa: F401
    except ImportError:
        print(
            "tetra3rs not installed. Re-run with:\n"
            "    uv run --with tetra3rs --with gaia-catalog python scripts/bench_solvers.py",
            file=sys.stderr,
        )
        return 2

    from importlib.metadata import version as _pkg_version

    print(
        f"# bench_solvers.py — {platform.machine()} / "
        f"python {platform.python_version()} / tetra3rs {_pkg_version('tetra3rs')}"
    )
    print()

    cols = "{:<10} {:>9} {:>10} {:>10} {:>9} {:>9} {:>10} {:>14}"
    print(
        cols.format(
            "sample", "t3 ms", "t3rs ms", "t3rs int", "sep ″", "Δroll °", "rmse ″", "matches t3/rs"
        )
    )
    print("-" * 95)

    rows = []
    for name in SAMPLES:
        p = SAMPLES_DIR / name
        if not p.exists():
            print(f"{name:<10} (missing)")
            continue
        a = solve_with_tetra3(p)
        b = solve_with_tetra3rs(p)

        if not (a["ok"] and b["ok"]):
            print(
                f"{name:<10} {a['ms_wall']:>9.1f} {b['ms_wall']:>10.1f} "
                f"  t3={'OK' if a['ok'] else 'FAIL'}  "
                f"t3rs={'OK' if b['ok'] else 'FAIL(' + str(b.get('status', '?')) + ', matches=' + str(b.get('matches')) + ', centroids=' + str(b.get('n_centroids')) + ')'}"
            )
            continue

        sep = angular_separation_arcsec(a["ra"], a["dec"], b["ra"], b["dec"])
        droll = wrap_signed_180(b["roll"] - a["roll"]) if a["roll"] is not None and b["roll"] is not None else float("nan")
        print(
            cols.format(
                name,
                f"{a['ms_wall']:.1f}",
                f"{b['ms_wall']:.1f}",
                f"{b['ms_internal']:.1f}",
                f"{sep:.1f}",
                f"{droll:+.3f}",
                f"{b['rmse_arcsec']:.2f}",
                f"{a['matches']}/{b['matches']}",
            )
        )
        rows.append((a, b))

    if rows:
        print()
        t3_avg = sum(r[0]["ms_wall"] for r in rows) / len(rows)
        t3rs_avg = sum(r[1]["ms_wall"] for r in rows) / len(rows)
        speedup = t3_avg / t3rs_avg if t3rs_avg else float("inf")
        print(
            f"avg wall: t3={t3_avg:.1f}ms  t3rs={t3rs_avg:.1f}ms  "
            f"speedup={speedup:.1f}×  (n={len(rows)})"
        )

        seps = [
            angular_separation_arcsec(a["ra"], a["dec"], b["ra"], b["dec"])
            for a, b in rows
        ]
        print(f"max RA/Dec disagreement: {max(seps):.1f}″ (mean {sum(seps) / len(seps):.1f}″)")

    print()
    print("Roll convention note: evf.solver negates tetra3 Roll (360 - r) to "
          "match its body-frame formulas; tetra3rs roll_deg uses its own "
          "convention. Δroll is informational only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
