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

## YAPP_Box/YAPPgenerator_v3.scad

- **Source:** https://github.com/mrWheel/YAPP_Box
- **Author:** Willem Aandewiel (with contributors listed in the file header)
- **License:** MIT — see `YAPP_Box/LICENSE`. The file also embeds part of
  Kurt Hutten's round-anything, under its own MIT notice at the end of the file.
- **Version:** v3.3.8 (2025-10-24), commit f9400c419ef1dea7dc0b3607876989b4f3faa2b7

Used by `housing_v4.scad` to generate the Raspberry Pi box (base and lid with a
ridge and snap joins). Only `YAPPgenerator_v3.scad` and `LICENSE` are vendored;
the upstream repo's prebuilt STLs, images and template are not needed.

Include it with `include <vendor/YAPP_Box/YAPPgenerator_v3.scad>`. Declaration
order matters: any helper variable used inside an assignment that YAPP also
declares a default for (`pcbStands`, `cutoutsLid`, …) must be declared *before*
the include, and helper names must not reuse YAPP's own names, or they silently
resolve to `undef` or to YAPP's defaults. YAPP's own settings are overridden
*after* the include.
