# Solver Performance — tetra3 vs tetra3rs

Measured 2026-05-18 via `scripts/bench_solvers.py` over the five frames
in `tests/samples/` (a, b, c, d, orion). tetra3 `solve_timeout` raised
to 15 s for the comparison so the slow Pi 4 cases run to completion.

## Laptop (Apple M-series, arm64)

| metric                       | tetra3 (Python) | tetra3rs (Rust) | speedup |
|------------------------------|----------------:|----------------:|--------:|
| wall-clock per frame         |    41–507 ms    |     24–37 ms    |    5.8× |
| solve hot loop only          |    (not timed)  |     0.2–2.1 ms  |       — |

Max RA/Dec disagreement: 21″ (mean 18″). RMSE 10–18″.

## Raspberry Pi 4 (Model B, 2 GB, aarch64, governor ondemand)

Wall-clock per frame (extraction + solve, both ends):

| sample    | t3 wall ms | t3rs wall ms | wall speedup |
|-----------|-----------:|-------------:|-------------:|
| a.png     |        268 |          214 |         1.3× |
| b.png     |       1673 |          218 |         7.7× |
| c.png     |        372 |          209 |         1.8× |
| d.png     |       6005 |          222 |        27.0× |
| orion.png |       2238 |          213 |        10.5× |
| **avg**   |   **2111** |      **215** |     **9.8×** |

Solve hot loop only (t3 = solve_from_centroids wall − centroid
extraction; t3rs = `SolveResult.solve_time_ms`):

| sample    | t3 solve ms | t3rs int ms | solve speedup |
|-----------|------------:|------------:|--------------:|
| a.png     |          15 |         4.9 |          3.1× |
| b.png     |        1453 |         0.9 |         1614× |
| c.png     |         141 |         1.7 |           83× |
| d.png     |        5929 |         7.6 |          780× |
| orion.png |        1902 |         7.7 |          247× |
| **avg**   |    **1888** |    **4.56** |       **414×** |

Max RA/Dec disagreement: 21.0″ (mean 18.2″). RMSE 10–18″.

## Observations

- Centroid extraction is ~200 ms per frame in both implementations on
  Pi 4 and effectively floors tetra3rs wall-clock at ~215 ms. Further
  wall-clock gains would require speeding up extraction, not the
  solver.
- tetra3's solve cost is unbounded in practice — easy frames finish in
  ~15 ms, hard frames take 1.5–6 s. tetra3rs caps at single-digit ms
  across all tested frames.
- The d.png case (5.9 s solve on Pi 4 pure-Python tetra3, 7.6 ms on
  tetra3rs) is the frame that motivates this work: unusable for
  real-time push-to on the existing solver, fully in budget on the new
  one.
- RA/Dec agreement between the two solvers (21″ max, 18″ mean) is
  identical on laptop and Pi 4. The accuracy story does not change
  with platform.
