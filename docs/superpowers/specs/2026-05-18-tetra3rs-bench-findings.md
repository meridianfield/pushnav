# tetra3rs sanity-check bench — findings

**Date:** 2026-05-18
**Status:** Sanity check complete, port not yet started
**Branch:** `rpi-appliance` (bench harness lives here)
**Successor:** A future `feat/tetra3rs` branch off main will do the
  actual wrapper port using these findings.

## Why this exists

The `_SOLVE_TIMEOUT_MS = 8000` hack that landed on `rpi-appliance` was a
stopgap — Pi 4 plate-solves take 1–6 s per frame on pure-Python tetra3,
which is unusable for real-time push-to. Notes from a prior investigation
(`~/Downloads/tetra3pi.md`, retained out-of-tree) pointed at `tetra3rs`
(MIT, GPL-compatible) as the path forward: same algorithm family
(cedar-solve / esa-tetra3), PyO3 Python bindings on PyPI, Rust hot loop
inside the same Python process — no subprocess, no IPC.

`scripts/bench_solvers.py` is the side-by-side sanity check before
touching any runtime code.

## What we found

### tetra3rs works on our test samples

All 5 frames in `tests/samples/` solve correctly with tetra3rs once the
extractor params are right. RA/Dec agreement with the existing tetra3
solver is **≤21″** across every frame (mean 18″) — well inside the
operational tolerance for an 8.86° FOV.

### Performance is decisive

Measured on laptop (M-series arm64, 2026-05-18). Pi 4 numbers TBD on
the successor branch:

| metric | tetra3 (Python) | tetra3rs (Rust) | ratio |
|---|---|---|---|
| wall-clock per frame | 41–507 ms (median ~150 ms) | 24–37 ms | **5.8× faster** |
| internal solve only | (not separately timed) | 0.2–2.1 ms | — |

The internal-solve number is the one that matters for Pi 4. Even with a
generous 5× ARM penalty, 1–10 ms internal on Pi 4 puts the solver well
inside any real-time budget. The wall-clock cost on tetra3rs is
dominated by centroid extraction, not the matmul.

### Centroid extraction parameters (CRITICAL)

This is the knowledge most worth preserving — it took several iterations
to find, and any future port will reuse it verbatim. The
`tetra3rs.extract_centroids` call must be:

```python
tetra3rs.extract_centroids(
    arr,
    sigma_threshold=5.0,
    max_pixels=2000,
    max_centroids=30,
    matched_filter_sigma=2.0,   # ← THE CRITICAL ONE
)
```

Mapping to tetra3's `get_centroids_from_image` settings:

| tetra3 | tetra3rs | role |
|---|---|---|
| `sigma=2` (Gaussian-blur sigma) | `matched_filter_sigma=2.0` | suppress extended emission (nebulae, etc.) so the brightest-N list is dominated by star-PSF responses |
| `max_area=2000` | `max_pixels=2000` | discard extended blobs |
| `pattern_checking_stars=30` | `max_centroids=30` | cap the matcher's input to brightest 30 |
| `filtsize=15` | (no direct equivalent) | not load-bearing in practice |

**Without `matched_filter_sigma=2.0`, orion.png fails** — M42's nebula
peaks rank above real stars in the brightest-30 list, and the 4-star
pattern hash picks 4 spurious peaks every time. The visually clearest
frame in the test set is the one that breaks without this parameter.

### Solver database parameters

Decoded from the existing `data/hip8_database.npz` via `props_packed`
(field order in `python/vendor/tetra3/tetra3/tetra3.py:524-555`):

```python
tetra3rs.SolverDatabase.generate_from_gaia(
    max_fov_deg=10.0,
    min_fov_deg=7.0,
    star_max_magnitude=8.0,
    pattern_max_error=0.005,
    verification_stars_per_fov=30,
    epoch_proper_motion_year=2026.0,
)
```

These match the hip8 db's settings. tetra3rs's bundled catalog is Gaia
DR3 + Hipparcos (vs Hipparcos-only in hip8), so the on-disk database
won't be byte-equivalent — but the resulting solves agree to within
~20″ on every sample.

The resulting `.bin` is **~53 MB at our FOV** (62k stars, 1.9M
patterns), vs ~85 MB for `hip8_database.npz`. The port should ship the
prebuilt `.bin` in `data/` rather than depending on `gaia-catalog` at
runtime.

### tetra3rs API quirks

These bit us during the bench; record them so the port doesn't repeat
them:

- `solve_from_centroids()` returns `None` on failure, not a
  `SolveResult` with a failed status field.
- `SolveStatus` values are lowercase: `"match_found"`, not `"MatchFound"`.
  Check via `"match_found" in str(result.status).lower()`.
- `SolverDatabase.num_stars` / `.num_patterns` / `.max_fov_deg` /
  `.min_fov_deg` are **properties**, not methods. No parens.
- `tetra3rs.version` is a function (the `importlib.metadata.version`
  re-export), not a `__version__` string. Use
  `importlib.metadata.version("tetra3rs")` directly.
- Hand-built `Centroid` objects use image-center origin (+X right,
  +Y down). `ExtractionResult.centroids` already in this frame; only
  matters if we feed centroids from another source.
- `SolveResult` exposes `matched_centroids` and `matched_catalog_ids`.
  Catalog star RA/Dec/mag comes via `db.get_star_by_id(id)`. This is
  the shape `evf/solver/sync.py` will need to consume after the port.

### Roll convention

`tetra3rs.SolveResult.roll_deg` is **~180° flipped** from our currently-
negated tetra3 Roll. Recall `evf.solver.solver.PlateSolver.solve_frame`
does `result["Roll"] = (360.0 - result["Roll"]) % 360.0`. The
tetra3rs port will need its own one-line adjustment — different sign
than the existing one. Empirically verified across all 5 test samples.

## What the port needs to do

Outline only — full plan lives on the successor branch:

1. Add `tetra3rs==0.7.1` and `gaia-catalog` as runtime deps in
   `pyproject.toml` (pin exactly — API is alpha per upstream README).
2. Drop the vendored tetra3 from `[tool.uv.sources]`. Keep
   `python/vendor/tetra3/` in tree for one release cycle as fallback;
   don't bundle it in the Nuitka build.
3. Generate the prebuilt `.bin` once during the build, commit to
   `data/tetra3rs_gaia.bin`, ship in place of `hip8_database.npz`.
4. Rewrite `python/evf/solver/solver.py` against the tetra3rs API,
   using the centroid + db params recorded above.
5. Update `python/evf/solver/sync.py` to consume `matched_centroids`
   + `matched_catalog_ids` (with `db.get_star_by_id`) instead of
   `matched_stars`. Verify calibration residuals still match.
6. Remove the `_IS_ARM` / `_SOLVE_TIMEOUT_MS` hack from `solver.py`
   (introduced on `rpi-appliance` as a Pi-only stopgap; obsolete once
   solves run in single-digit ms everywhere).
7. Bench on Pi 4 to confirm the projected 1–10 ms internal solve.
8. Soak-test, then drop `python/vendor/tetra3/` after one release.

## Rollback

If the tetra3rs path regresses in production and we need to revert to
the legacy pure-Python tetra3 quickly:

1. Re-add the tetra3 source dep to `pyproject.toml`:
   ```toml
   [tool.uv.sources]
   tetra3 = { path = "python/vendor/tetra3", editable = true }
   ```
   and swap `tetra3rs==0.7.1` for `tetra3` in `[project] dependencies`.

2. Restore the old solver: `git show 823adf3:python/evf/solver/solver.py
   > python/evf/solver/solver.py`. The legacy hip8 database is still on
   disk at `data/hip8_database.npz` and the vendored sources are at
   `python/vendor/tetra3/`.

3. Run `uv sync` and `uv run pytest tests/` — all tests should pass on
   the legacy solver too.

These artifacts stay in tree for one release cycle as the safety net;
they should be deleted in a follow-up cleanup after a stable release on
the new solver.

## How to re-run the bench

```bash
# laptop or Pi 4 (after `uv sync`):
uv run --with tetra3rs --with gaia-catalog --with numpy --with Pillow \
    python scripts/bench_solvers.py
```

First run regenerates `.cache/tetra3rs_gaia.bin` (~3 s on laptop).
Subsequent runs load from cache.
