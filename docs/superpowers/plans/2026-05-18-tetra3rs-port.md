# tetra3rs Solver Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pure-Python `tetra3` plate solver with the Rust-backed `tetra3rs` across all platforms (laptop + Pi 4 + future Pi Zero 2), in a single drop-in swap that preserves the engine's external behaviour.

**Architecture:** `PlateSolver` in `python/evf/solver/solver.py` is rewritten internally to call `tetra3rs` (PyO3 Python bindings to the Rust crate) instead of vendored `tetra3`. The public surface — `PlateSolver()` constructor, `solve_frame(image_bytes) -> dict`, `is_valid(result)` — and the result-dict keys (`RA`, `Dec`, `Roll`, `Matches`, `Prob`, `matched_centroids`, `matched_stars`, `all_centroids`, `image_size`, `T_extract`, `T_solve`) stay byte-identical so nothing in `solver/thread.py`, `solver/sync.py`, `engine/engine.py`, or `webserver/server.py` has to change. A new prebuilt catalog `.bin` (~53 MB) replaces the 85 MB `hip8_database.npz` in `data/`. Vendored `tetra3` sources and `hip8_database.npz` remain in tree for one release cycle as a revertible fallback; they are not bundled into release builds.

**Tech Stack:** `tetra3rs==0.7.1` (MIT, GPL-3 compatible) runtime dep; `gaia-catalog` is a transitive runtime dep of `tetra3rs` (pulled automatically — not declared explicitly in our dev group); PyO3 wheels for macOS arm64, Linux x86_64+aarch64, Windows x86_64 (already verified on PyPI). No build-time Rust toolchain required on any supported platform.

**Inputs to this plan:**
- `specs/start/SPEC_SOLVER_PERFORMANCE.md` — Pi 4 + laptop perf measurements (414× internal speedup avg, 18″ RA/Dec agreement)
- `docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md` — extractor params (`matched_filter_sigma=2.0`, `max_pixels=2000`, `max_centroids=30`), db params (decoded from `hip8_database.npz` props_packed), tetra3rs API quirks, roll convention
- `scripts/bench_solvers.py` — the harness used throughout the port for regression checking

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `pyproject.toml` | modify | Add `tetra3rs==0.7.1` runtime dep, `gaia-catalog` dev dep, drop `[tool.uv.sources]` tetra3 entry. |
| `python/evf/paths.py` | modify | Add `tetra3rs_database_path()` returning `.../data/tetra3rs_gaia.bin` (dev/macOS/Linux/Windows release variants). Keep existing `database_path()` for now (one consumer left after the port: it can be removed in the cleanup follow-up). |
| `python/evf/solver/solver.py` | rewrite | `PlateSolver` class. Same external API, internals now call `tetra3rs.SolverDatabase.load_from_file()` + `tetra3rs.extract_centroids()` + `solve_from_centroids()`. Result dict shape unchanged. |
| `scripts/build_tetra3rs_catalog.py` | create | One-shot dev script that builds `data/tetra3rs_gaia.bin` from the bundled `gaia-catalog` using the exact same db params as the bench (`min_fov=7°`, `max_fov=10°`, `star_max_magnitude=8`, `pattern_max_error=0.005`, `verification_stars_per_fov=30`, `epoch_proper_motion_year=2026.0`). |
| `data/tetra3rs_gaia.bin` | create (committed) | Pre-generated catalog `.bin`, ~53 MB. Shipped in all release builds. |
| `data/VERSION.json` | modify | Replace `hip_db_version` with `solver_db_version: "tetra3rs_gaia_<git-sha>_mag8"`. |
| `scripts/build_linux.sh` | modify | Bundle `tetra3rs_gaia.bin` instead of `hip8_database.npz`. |
| `scripts/build_mac.sh` | modify | Same. |
| `scripts/build_windows.bat` | modify | Same. |
| `tests/test_solver_offline.py` | extend | Add a Roll-regression test that locks in the new (tetra3rs) Roll convention against known-good values measured during the bench. Existing RA/Dec tests should pass unchanged. |
| `data/hip8_database.npz` | retain (not bundled) | Stays in repo for one release cycle as a revertible fallback. |
| `python/vendor/tetra3/` | retain (not imported) | Stays in repo for one release cycle. Removed from `[tool.uv.sources]` so `uv sync` no longer installs it. |
| `specs/start/SPEC_SOLVER_PERFORMANCE.md` | retain | Already on the branch; no edits needed during the port. |

**No changes required** to `python/evf/solver/sync.py`, `python/evf/solver/thread.py`, `python/evf/engine/engine.py`, `python/evf/engine/pointing.py`, `python/evf/webserver/server.py`, `python/evf/engine/navigation.py`, or `tests/test_sync.py` — all are downstream consumers of the result-dict shape that solver.py maintains.

---

## Task 1: Add tetra3rs runtime dep, gaia-catalog dev dep

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1.1: Edit `pyproject.toml`**

Replace the `[project] dependencies` block by adding `tetra3rs==0.7.1` and removing `tetra3`, and add `gaia-catalog` to the dev group:

```toml
[project]
name = "evf"
version = "0.2.0"
requires-python = ">=3.12,<3.14"
dependencies = [
    "Pillow",
    "numpy",
    "scipy",
    "tetra3rs==0.7.1",
    "playsound3",
    "aiohttp",
    "qrcode[pil]",
    "pyerfa>=2.0.0",
    "pywebview>=5.0",
    "pywebview[qt]>=5.0 ; sys_platform == 'linux'",
]

[dependency-groups]
dev = [
    "nuitka>=4.0.2",
    "pytest",
    "pytest-asyncio>=0.23",
    "gaia-catalog",
    "dmgbuild>=1.6.5; sys_platform == 'darwin'",
]
```

Delete the entire `[tool.uv.sources]` section (only line was `tetra3 = { path = "python/vendor/tetra3", editable = true }`).

- [ ] **Step 1.2: Run `uv sync` and verify**

Run: `uv sync`
Expected: deps resolve, `tetra3rs` 0.7.1 installs from wheel, `gaia-catalog` installs into the dev group. No `tetra3` left in the venv.

Verify:

```bash
uv run python -c "import tetra3rs; print(tetra3rs.__file__)"
```

Expected: prints a path inside `.venv/lib/python3.12/site-packages/tetra3rs/`.

```bash
uv run python -c "import tetra3" 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'tetra3'` — confirms the vendored editable dep is gone (file still on disk under `python/vendor/tetra3/` but not installed).

- [ ] **Step 1.3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: swap vendored tetra3 → tetra3rs==0.7.1 (gaia-catalog as dev dep)"
```

---

## Task 2: Add `tetra3rs_database_path()` to paths.py

**Files:**
- Modify: `python/evf/paths.py`

- [ ] **Step 2.1: Add the new path resolver**

In `python/evf/paths.py`, immediately after the existing `database_path()` function (currently at lines 75–81), add:

```python
def tetra3rs_database_path() -> Path:
    """Path to the prebuilt tetra3rs SolverDatabase .bin.

    Generated by scripts/build_tetra3rs_catalog.py from the bundled
    gaia-catalog package; shipped in data/ for all builds.
    """
    if _BUNDLE_MODE:
        return _RESOURCES / "tetra3rs_gaia.bin"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "tetra3rs_gaia.bin"
    return _REPO_ROOT / "data" / "tetra3rs_gaia.bin"
```

Leave `database_path()` in place — it will become orphaned after Task 4 but stays one release for revertibility.

- [ ] **Step 2.2: Smoke-test from a Python shell**

Run:

```bash
uv run python -c "from evf.paths import tetra3rs_database_path; print(tetra3rs_database_path())"
```

Expected: prints `/Users/arun/Devel/Github/pushnav/data/tetra3rs_gaia.bin` (file doesn't exist yet — that's expected, comes in Task 3).

- [ ] **Step 2.3: Commit**

```bash
git add python/evf/paths.py
git commit -m "paths: add tetra3rs_database_path() resolver"
```

---

## Task 3: Build and commit the tetra3rs catalog .bin

**Files:**
- Create: `scripts/build_tetra3rs_catalog.py`
- Create (committed binary): `data/tetra3rs_gaia.bin`
- Modify: `data/VERSION.json`

- [ ] **Step 3.1: Write `scripts/build_tetra3rs_catalog.py`**

```python
#!/usr/bin/env python3
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
```

- [ ] **Step 3.2: Run the build script**

Run:

```bash
uv run --group dev python scripts/build_tetra3rs_catalog.py
```

Expected output (numbers approximate):

```
Generating tetra3rs db (FOV 7.0°..10.0°, mag<=8.0)...
Built in 3.4s (62793 stars, 1914984 patterns), wrote data/tetra3rs_gaia.bin (5.2 MB)
```

Verify the file:

```bash
ls -la data/tetra3rs_gaia.bin
```

Expected: file exists, ~53 MB.

- [ ] **Step 3.3: Verify the `.bin` loads without `gaia-catalog`**

Confirm the runtime path does NOT need the `gaia-catalog` dev dep (the build dep). Temporarily uninstall it and reload:

```bash
uv run python -c "
import tetra3rs
db = tetra3rs.SolverDatabase.load_from_file('data/tetra3rs_gaia.bin')
print(f'loaded: {db.num_stars} stars, {db.num_patterns} patterns')
"
```

Expected: prints `loaded: 62793 stars, 1914984 patterns` (or close) — no `gaia-catalog` ImportError. (`gaia-catalog` is in the dev group but loading a pre-built `.bin` shouldn't need it. If this fails, escalate before continuing — `gaia-catalog` may need to be a runtime dep after all.)

- [ ] **Step 3.4: Update `data/VERSION.json`**

Get the size and a deterministic content hash for the version key:

```bash
shasum -a 256 data/tetra3rs_gaia.bin | cut -c1-12
```

Edit `data/VERSION.json` to replace `hip_db_version` with `solver_db_version`:

```json
{
  "app_version": "0.2.0",
  "protocol_version": 1,
  "solver_db_version": "tetra3rs_gaia_<paste-the-12-char-hash>_mag8"
}
```

- [ ] **Step 3.5: Commit**

```bash
git add scripts/build_tetra3rs_catalog.py data/tetra3rs_gaia.bin data/VERSION.json
git commit -m "data: prebuilt tetra3rs SolverDatabase catalog (~53 MB, mag<=8, FOV 7°-10°)"
```

---

## Task 4: Rewrite solver.py against tetra3rs

**Files:**
- Modify (full rewrite): `python/evf/solver/solver.py`
- Existing tests: `tests/test_solver_offline.py`, `tests/test_offline_full.py`, `tests/test_sync.py` (all should continue to pass)

The existing tests in `tests/test_solver_offline.py` cover the external contract (RA/Dec within 2° on 4 samples; `Matches >= 8`; `Prob <= 0.2`; `is_valid()` behavior). They are the regression-check; we keep them unchanged and make the new implementation satisfy them.

- [ ] **Step 4.1: Inspect the existing test contract**

Read `tests/test_solver_offline.py` and confirm these expectations exist and will NOT be modified:

- `solver.solve_frame(image_bytes)["RA"]` within 2° of expected
- `result["Dec"]` within 2° of expected
- `result["Matches"] >= 8`
- `result["Prob"] <= 0.2`
- `PlateSolver.is_valid(result, min_matches=N, max_prob=P)` predicate

Also confirm `python/evf/solver/thread.py` consumes: `RA`, `Dec`, `Roll`, `Matches`, `Prob`, `T_extract`, `T_solve`, `all_centroids`, `matched_centroids`, `image_size`. And `python/evf/engine/engine.py:624` consumes `matched_centroids`, `matched_stars`, `image_size`. And `python/evf/solver/sync.py:174` expects `matched_centroids[i] = [y, x]` and `matched_stars[i] = [ra_deg, dec_deg, mag]`.

These are the contracts the rewrite must preserve.

- [ ] **Step 4.2: Write the new solver.py**

Replace `python/evf/solver/solver.py` (whole file):

```python
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

"""Plate solver — tetra3rs wrapper for single-frame plate solving.

Internals use the Rust-backed tetra3rs (MIT, GPL-3 compatible). The
external API and result-dict shape match the legacy tetra3 wrapper so
the rest of the engine is unchanged. See
docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md for the
parameter rationale and tetra3rs API quirks.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import numpy as np
import tetra3rs
from PIL import Image

from evf.paths import tetra3rs_database_path

logger = logging.getLogger(__name__)

_DATABASE_PATH = tetra3rs_database_path()

# Centroid extraction parameters — see the bench-findings doc for why
# matched_filter_sigma=2.0 is load-bearing (without it, M42 nebulosity
# crowds out real stars in the brightest-N list and orion.png fails).
_CENTROID_PARAMS = dict(
    sigma_threshold=5.0,
    max_pixels=2000,
    max_centroids=30,
    matched_filter_sigma=2.0,
)

# Solve parameters mirroring the legacy tetra3 settings. tetra3rs's
# match_threshold (1e-5 default) is the false-positive cap on internal
# acceptance; it differs in semantic from tetra3's old match_threshold
# (0.1) and we keep the tetra3rs default. The resulting
# SolveResult.probability is what we expose as "Prob" and gate via
# is_valid(max_prob=...) — the existing 0.2 threshold remains
# trivially satisfied since tetra3rs only returns results well under
# its own 1e-5 internal threshold.
_FOV_DEG = 8.86
_FOV_MAX_ERROR_DEG = 1.5


class PlateSolver:
    """Load tetra3rs database once and solve frames on demand."""

    def __init__(self, database_path: Path | None = None) -> None:
        db_path = database_path or _DATABASE_PATH
        t0 = time.monotonic()
        self._db = tetra3rs.SolverDatabase.load_from_file(str(db_path))
        elapsed = time.monotonic() - t0
        logger.info(
            "tetra3rs database loaded in %.2fs: %s (%d stars, %d patterns)",
            elapsed, db_path, self._db.num_stars, self._db.num_patterns,
        )

    def solve_frame(self, image_bytes: bytes) -> dict:
        """Solve a single image frame. Returns a tetra3-compatible result dict.

        Keys returned (preserving the legacy contract):
          RA, Dec, Roll          — degrees, J2000
          Matches                — number of matched stars (int)
          Prob                   — false-positive probability (float)
          T_extract              — centroid extraction time, ms
          T_solve                — solver internal time, ms
          all_centroids          — list[[y, x], ...] top-left-origin pixels
          matched_centroids      — list[[y, x], ...] top-left-origin pixels
          matched_stars          — list[[ra_deg, dec_deg, mag], ...]
          image_size             — (height, width)

        On unsolvable frames, RA/Dec/Roll/Matches/Prob are None / 0 and
        the centroid lists are populated only when extraction itself
        succeeded.
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        arr = np.asarray(img, dtype=np.float64)
        h, w = arr.shape

        t0 = time.monotonic()
        extraction = tetra3rs.extract_centroids(arr, **_CENTROID_PARAMS)
        t_extract_ms = (time.monotonic() - t0) * 1000

        all_centroids = self._centroids_to_yx(extraction.centroids, h, w)

        t0 = time.monotonic()
        result = self._db.solve_from_centroids(
            extraction.centroids,
            fov_estimate_deg=_FOV_DEG,
            fov_max_error_deg=_FOV_MAX_ERROR_DEG,
            image_shape=(h, w),
        )
        t_solve_ms = (time.monotonic() - t0) * 1000

        out: dict = {
            "RA": None,
            "Dec": None,
            "Roll": None,
            "Matches": 0,
            "Prob": None,
            "T_extract": t_extract_ms,
            "T_solve": t_solve_ms,
            "all_centroids": all_centroids,
            "matched_centroids": [],
            "matched_stars": [],
            "image_size": (h, w),
        }

        if result is None or "match_found" not in str(result.status).lower():
            return out

        # Roll convention: tetra3rs roll_deg is ~180° flipped from the
        # legacy evf result (which negated tetra3's Roll as `360 - r`).
        # Empirically verified across the five test samples.
        roll = (result.roll_deg + 180.0) % 360.0

        matched_centroids = self._centroids_to_yx(result.matched_centroids, h, w)
        matched_stars = self._catalog_ids_to_radec_mag(result.matched_catalog_ids)

        out.update({
            "RA": result.ra_deg,
            "Dec": result.dec_deg,
            "Roll": roll,
            "Matches": result.num_matches or 0,
            "Prob": result.probability,
            "matched_centroids": matched_centroids,
            "matched_stars": matched_stars,
        })
        return out

    def _centroids_to_yx(self, centroids, h: int, w: int) -> list:
        """Convert tetra3rs Centroids (image-center origin, +X right,
        +Y down) to legacy [y, x] top-left-origin pixel coords."""
        cx, cy = w / 2.0, h / 2.0
        out = []
        for c in centroids:
            x_tl = c.x + cx
            y_tl = c.y + cy
            out.append([float(y_tl), float(x_tl)])
        return out

    def _catalog_ids_to_radec_mag(self, ids) -> list:
        """Build the legacy [[ra_deg, dec_deg, mag], ...] list from
        tetra3rs catalog ids via db.get_star_by_id()."""
        out = []
        for sid in ids:
            star = self._db.get_star_by_id(int(sid))
            out.append([float(star.ra_deg), float(star.dec_deg), float(star.mag)])
        return out

    @staticmethod
    def is_valid(
        result: dict, min_matches: int = 8, max_prob: float = 0.2
    ) -> bool:
        """Check if a solve result meets quality thresholds."""
        if result.get("RA") is None:
            return False
        if result.get("Matches", 0) < min_matches:
            return False
        if result.get("Prob", 1.0) > max_prob:
            return False
        return True
```

> **API surface verification before implementing:** while writing this file, verify the `CatalogStar` returned by `db.get_star_by_id()` actually exposes `ra_deg`, `dec_deg`, `mag`. If the attribute names differ (e.g. `magnitude`, `ra`, `dec`), adjust `_catalog_ids_to_radec_mag` accordingly. Quick probe:
>
> ```bash
> uv run python -c "
> import tetra3rs
> db = tetra3rs.SolverDatabase.load_from_file('data/tetra3rs_gaia.bin')
> star = db.get_star_by_id(1)
> print([a for a in dir(star) if not a.startswith('_')])
> "
> ```
>
> If the attributes differ, edit the helper accordingly before moving on.

- [ ] **Step 4.3: Run the offline solver tests**

Run:

```bash
uv run pytest tests/test_solver_offline.py -v
```

Expected: all 12 tests pass.

- `TestOfflineSolve::test_solve_image[a.png-...]` — RA/Dec within 2°, Matches >= 8, Prob <= 0.2
- `TestOfflineSolve::test_solve_image[b.png-...]`
- `TestOfflineSolve::test_solve_image[c.png-...]`
- `TestOfflineSolve::test_solve_image[d.png-...]`
- `TestIsValid` (5 tests)
- `TestSolverThread` (3 tests)

If any RA/Dec test fails by more than 2°, the most likely cause is a sign error in the centroid coordinate translation (image-center → top-left) or a wrong Roll sign — debug before proceeding.

- [ ] **Step 4.4: Run the full test suite**

Run:

```bash
uv run pytest tests/ -v 2>&1 | tail -50
```

Expected: every existing test passes. The sync.py tests (`tests/test_sync.py`) and the full-engine tests (`tests/test_offline_full.py`) should be unaffected.

- [ ] **Step 4.5: Run the bench harness to confirm parity with rpi-appliance numbers**

Run:

```bash
uv run --with numpy --with Pillow python scripts/bench_solvers.py 2>&1 | tail -12
```

Expected: 5/5 solving, mean RA/Dec disagreement ≤ ~25″, avg wall-clock comparable to baseline (~30 ms on M-series laptop). The bench loads tetra3 from the disappeared dep, so this will fail with ImportError unless we ALSO patch the bench script. **Defer the bench patch to Task 7** — the test-suite output is enough to validate Task 4.

- [ ] **Step 4.6: Commit**

```bash
git add python/evf/solver/solver.py
git commit -m "solver: drop-in rewrite against tetra3rs (preserves result-dict shape)"
```

---

## Task 5: Roll-convention regression test

**Files:**
- Modify: `tests/test_solver_offline.py`

The Roll sign is the highest-risk subtle bug — it's a single-line algebra fix (`(roll_deg + 180) % 360`) that's easy to invert. `tests/test_sync.py` doesn't run the solver, so it won't catch a wrong Roll. We add an explicit lock-in test against measured values.

- [ ] **Step 5.1: Capture known-good Roll values**

Run the bench once and copy the Roll column from the solver output for each sample (run with DOWNSAMPLE=1 baseline):

```bash
uv run --with numpy --with Pillow python scripts/bench_solvers.py 2>&1
```

(Skip — those values are already captured by being on this branch. Use the baseline values measured during `c56ee85`: Roll on each sample is what evf.solver.PlateSolver produced. After this port, the new solver's Roll should match the old one to within ~1° because we explicitly account for the 180° convention difference.)

The cleanest way to obtain the lock-in values: solve each sample with the just-rewritten solver and snapshot the result.

```bash
uv run python -c "
from pathlib import Path
from evf.solver.solver import PlateSolver
s = PlateSolver()
for name in ['a.png', 'b.png', 'c.png', 'd.png']:
    res = s.solve_frame((Path('tests/samples') / name).read_bytes())
    print(f'  ({name!r}, {res[\"Roll\"]:.3f}),')
"
```

Copy the four `(name, roll)` tuples printed.

- [ ] **Step 5.2: Add the Roll regression test**

In `tests/test_solver_offline.py`, after the `TestOfflineSolve` class, add:

```python
class TestRollRegression:
    """Lock in the Roll convention. tetra3rs roll_deg is 180° flipped
    from tetra3's negated convention; the wrapper corrects to match
    the body-frame formulas in solver/sync.py. A sign error here is
    silent until sync calibration fails on real hardware.
    """

    # Values captured from the tetra3rs wrapper at port time.
    # Tolerance is loose (5°) because RA/Dec refinement also nudges
    # Roll; what we're really testing is the convention sign, not
    # exact arithmetic.
    @pytest.mark.parametrize(
        "image_name,expected_roll",
        [
            # FILL IN from Step 5.1
            ("a.png", <FILL_IN_FROM_STEP_5_1>),
            ("b.png", <FILL_IN_FROM_STEP_5_1>),
            ("c.png", <FILL_IN_FROM_STEP_5_1>),
            ("d.png", <FILL_IN_FROM_STEP_5_1>),
        ],
    )
    def test_roll_sign(self, solver, image_name, expected_roll):
        image_bytes = (_SAMPLES_DIR / image_name).read_bytes()
        result = solver.solve_frame(image_bytes)
        assert result["Roll"] is not None
        diff = abs(((result["Roll"] - expected_roll) + 180) % 360 - 180)
        assert diff < 5.0, (
            f"{image_name}: Roll={result['Roll']:.2f}, "
            f"expected {expected_roll:.2f}, |diff|={diff:.2f}° "
            f"— check the (+180) % 360 convention in solver.py"
        )
```

- [ ] **Step 5.3: Run the new test**

Run:

```bash
uv run pytest tests/test_solver_offline.py::TestRollRegression -v
```

Expected: 4 passes. (If the values were captured in Step 5.1 from the same code under test, this should always pass at first run — it's locking in for future regressions.)

- [ ] **Step 5.4: Commit**

```bash
git add tests/test_solver_offline.py
git commit -m "tests: lock in Roll convention against silent sign-flip regressions"
```

---

## Task 6: Update build scripts to ship the new .bin

**Files:**
- Modify: `scripts/build_linux.sh:122`
- Modify: `scripts/build_mac.sh:152`
- Modify: `scripts/build_windows.bat:138`

- [ ] **Step 6.1: Patch `scripts/build_linux.sh`**

Find the line:

```bash
cp "$REPO_ROOT/data/hip8_database.npz" "$APP_DIR/data/"
```

Replace with:

```bash
cp "$REPO_ROOT/data/tetra3rs_gaia.bin" "$APP_DIR/data/"
```

- [ ] **Step 6.2: Patch `scripts/build_mac.sh`**

Find:

```bash
cp "$REPO_ROOT/data/hip8_database.npz" "$RESOURCES/"
```

Replace with:

```bash
cp "$REPO_ROOT/data/tetra3rs_gaia.bin" "$RESOURCES/"
```

- [ ] **Step 6.3: Patch `scripts/build_windows.bat`**

Find:

```bat
copy /y "%REPO_ROOT%\data\hip8_database.npz" "%APP_DIR%\data\"
```

Replace with:

```bat
copy /y "%REPO_ROOT%\data\tetra3rs_gaia.bin" "%APP_DIR%\data\"
```

- [ ] **Step 6.4: Smoke-test the macOS build script (on this laptop)**

Run:

```bash
scripts/build_mac.sh 2>&1 | tail -30
```

Expected: build completes (Nuitka warnings are OK), the resulting `.app` contains `Contents/Resources/tetra3rs_gaia.bin` and does NOT contain `hip8_database.npz`:

```bash
find build/ -name 'tetra3rs_gaia.bin' -o -name 'hip8_database.npz'
```

Expected: prints only the `tetra3rs_gaia.bin` paths.

(Skip Linux + Windows scripts on this laptop — they can be smoke-tested in their respective environments later. The Nuitka build on macOS is sufficient to validate the cp/path patterns.)

- [ ] **Step 6.5: Commit**

```bash
git add scripts/build_linux.sh scripts/build_mac.sh scripts/build_windows.bat
git commit -m "build: ship tetra3rs_gaia.bin instead of hip8_database.npz"
```

---

## Task 7: Update bench_solvers.py to remove tetra3 and use the prebuilt .bin

**Files:**
- Modify: `scripts/bench_solvers.py`

After Task 1, `tetra3` is no longer importable in this venv. The bench script's `solve_with_tetra3` function will fail at import time. It's still useful as a tetra3rs-only perf harness — strip the tetra3 path and rename appropriately.

- [ ] **Step 7.1: Strip the tetra3 path from `scripts/bench_solvers.py`**

Open `scripts/bench_solvers.py` and:

1. Delete the entire `solve_with_tetra3()` function (currently ~25 lines).
2. Delete the `_t3_solver = None` module-level placeholder.
3. In `main()`, replace the side-by-side table with a tetra3rs-only one. Remove the `a` (tetra3) calls and just print `b` (tetra3rs). Remove `sep ″` and `Δroll °` and `matches t3/rs` columns; keep `t3rs ms`, `t3rs int`, `rmse ″`, `matches`. Update the avg-wall summary line to drop the `speedup=N×` term (or replace with a "vs baseline N×" referencing `SPEC_SOLVER_PERFORMANCE.md`).
4. Update the module docstring: remove all references to "side-by-side" comparison; the bench is now a tetra3rs-only quality/perf harness.
5. Update the catalog-generation path: the bench should *load* `data/tetra3rs_gaia.bin` (the committed prebuilt) and only fall back to regenerating into `.cache/` if that file is missing. The `data/`-loaded path is the production behaviour and what we want to measure.

(This task is a mechanical edit — the existing script structure is clear; just remove the tetra3 columns and prefer the data/ .bin over the .cache one.)

- [ ] **Step 7.2: Run the updated bench**

Run:

```bash
uv run --with numpy --with Pillow python scripts/bench_solvers.py 2>&1 | tail -10
```

Expected: 5/5 solving, avg wall ~30 ms on laptop, no ImportError, loads from `data/tetra3rs_gaia.bin`.

- [ ] **Step 7.3: Commit**

```bash
git add scripts/bench_solvers.py
git commit -m "bench: strip tetra3 path; tetra3rs-only against the committed prebuilt .bin"
```

---

## Task 8: End-to-end smoke test of the running engine

**Files:** none (verification only)

- [ ] **Step 8.1: Launch the engine in dev mode**

Run:

```bash
PUSHNAV_DEBUG=1 uv run python -m evf.main --dev --no-window 2>&1 | tee /tmp/pushnav-port-smoke.log &
ENGINE_PID=$!
sleep 8
```

Expected log lines within 8 seconds (in any order):

- `tetra3rs database loaded in N.NNs: .../data/tetra3rs_gaia.bin (62793 stars, ...)`
- `Stellarium server listening on 127.0.0.1:10001`
- `LX200 server listening on 0.0.0.0:4030`
- `Mobile web interface at http://...:8765`
- NO mentions of `tetra3` (without the `rs`) and NO `hip8_database`.

- [ ] **Step 8.2: Inject a sample frame via the debug endpoint**

While the engine is still running:

```bash
curl -X POST 'http://127.0.0.1:8765/api/debug/inject?sample=b.png'
sleep 2
curl -s 'http://127.0.0.1:8765/api/state' | python -m json.tool | head -25
```

Expected: `"state": "TRACKING"` (or `"SYNC"` depending on engine init path), and `ra_j2000`/`dec_j2000` near 132.88 / 46.37. Centroid arrays populated.

- [ ] **Step 8.3: Shut the engine down cleanly**

```bash
kill -INT $ENGINE_PID
wait $ENGINE_PID
```

Expected: clean shutdown, exit code 0, no Python tracebacks in the log.

- [ ] **Step 8.4: Note any anomalies**

If the engine fails to start or the smoke endpoint returns a stale state, file the issue inline and stop. Do not commit the port until the engine boots cleanly with the new solver.

- [ ] **Step 8.5: Commit a small note in `SPEC_SOLVER_PERFORMANCE.md`** (optional housekeeping)

Add a one-line entry under the existing tables noting "Engine smoke-tested with tetra3rs on 2026-05-18 (commit <SHA>)" so the spec doc records when the swap actually landed. Skip if it feels like clutter.

```bash
git add specs/start/SPEC_SOLVER_PERFORMANCE.md
git commit -m "spec(solver): record tetra3rs port landing"
```

---

## Task 9: Pi 4 validation (manual checkpoint)

This is a hand-off task — the user runs it on their Pi 4. The plan documents the expected outcome so the Pi-side Claude (or the user) knows what "good" looks like.

- [ ] **Step 9.1: Push the branch**

```bash
git push
```

- [ ] **Step 9.2: On the Pi 4 — pull and uv sync**

```bash
git fetch
git checkout feat/tetra3rs
git pull
uv sync
```

Expected: `tetra3rs` 0.7.1 manylinux_2_28_aarch64 wheel installs; no Rust toolchain invoked; `gaia-catalog` is dev-only so isn't downloaded.

- [ ] **Step 9.3: On the Pi 4 — run the test suite**

```bash
uv run pytest tests/ 2>&1 | tail -20
```

Expected: same results as on the laptop (5/5 offline-solve tests pass, sync tests pass, etc.).

- [ ] **Step 9.4: On the Pi 4 — bench**

```bash
uv run --with numpy --with Pillow python scripts/bench_solvers.py 2>&1 | tail -10
```

Expected: 5/5 solving, t3rs internal solve avg ~4–5 ms (matching the pre-port Pi 4 numbers measured in `SPEC_SOLVER_PERFORMANCE.md`). Wall-clock per frame ~215 ms (extraction-bound).

- [ ] **Step 9.5: On the Pi 4 — smoke-test the running engine**

Same as Task 8 but on the Pi. Verify `tetra3rs database loaded ...` line appears in the startup log.

- [ ] **Step 9.6: Report back**

If all four checks pass, the port is verified end-to-end. If any fail, file the issue on the branch and stop.

---

## Self-Review Checklist (run before handoff)

- [ ] **Spec coverage:** every requirement listed in `docs/superpowers/specs/2026-05-18-tetra3rs-bench-findings.md` § "What the port needs to do" maps to a task above:
  - Add tetra3rs as runtime dep ✓ Task 1
  - Drop tetra3 from [tool.uv.sources] ✓ Task 1
  - Ship prebuilt .bin in data/ ✓ Task 3
  - Rewrite solver.py against tetra3rs API ✓ Task 4
  - Use the captured centroid + db params ✓ Task 4 (`_CENTROID_PARAMS`)
  - sync.py works unchanged ✓ Task 4 contract preserves matched_stars/matched_centroids shape; Task 5 locks in Roll
  - Remove `_IS_ARM` / `_SOLVE_TIMEOUT_MS` hack — N/A on this branch (lives on `rpi-appliance`)
  - Bench on Pi 4 ✓ Task 9
  - Drop `python/vendor/tetra3/` after one release — explicitly deferred to a follow-up

- [ ] **No placeholders:** every code block is complete except the explicitly-marked `<FILL_IN_FROM_STEP_5_1>` in Task 5.2, which is filled by Step 5.1 of the same task.

- [ ] **Type consistency:** result dict keys in Task 4's `solver.py` match the keys consumed in `solver/thread.py` and `engine/engine.py` (verified during exploration: RA, Dec, Roll, Matches, Prob, T_extract, T_solve, all_centroids, matched_centroids, matched_stars, image_size).

- [ ] **Risk: CatalogStar attribute names.** Task 4 Step 4.2 includes an inline probe step to verify `star.ra_deg/dec_deg/mag` field names before committing.

- [ ] **Risk: tetra3rs.SolveResult.probability scale.** The new wrapper exposes it verbatim as `Prob`. Existing `is_valid(max_prob=0.2)` stays trivially satisfied because tetra3rs only returns results with `probability <= match_threshold=1e-5`. If post-port the engine sees `is_valid` returning False unexpectedly, the gate is `Matches < min_matches`, not `Prob`.

---

## Execution Handoff

Once the user confirms the plan, execute via one of:

- **Subagent-driven** (recommended): fresh subagent per task, two-stage review between tasks. Best for safety on a port that touches deps + data + runtime code at once.
- **Inline** in this session: execute task-by-task with the user reviewing after each commit. Faster, lower ceremony.
