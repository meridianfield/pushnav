# Vendored OpenSCAD libraries

## threads.scad

- **Source:** https://github.com/rcolyer/threads-scad
- **Author:** Ryan A. Colyer
- **License:** CC0-1.0 (public domain dedication)
- **Version:** v2.1

Used by `housing_v2.scad` for the female-threaded lip on the PCB base.
Provides `ScrewHole(outer_diam, height, ..., pitch, tooth_angle, tolerance)`
for cutting internal threads into children, plus matching `ScrewThread()` for
male threads on a cap.
