# PushNav 3D Models

3D-printable parts for the PushNav camera system. All models are written in [OpenSCAD](https://openscad.org/) for FDM printing. The hood, cap, and accessories print without supports; the base needs localised slicer supports (see [Print Settings](#print-settings)).

## Parts

### Camera Housing v3 (`housing_v3.scad`) — rotation adjustment (new)

Same camera pocket and threaded hood as v2, but the housing **turns about the optical axis** on a separate dovetail mount, so the camera's up/down and left/right line up with the telescope's even when the finder shoe sits at an angle. Loosen the knob behind the mount, turn the camera until the app's mount axes look square with the screen, tighten, and recalibrate.

Four parts controlled by `RENDER_*` flags (with one flag on, the part is placed in its print orientation):

| Part | Flag | Description |
|------|------|-------------|
| Mount | `RENDER_MOUNT` | Finder-shoe dovetail, low bridge rib, and a flat Ø30 seat the housing turns on |
| PCB Base + Lip | `RENDER_BASE` | v2's 50 mm shell, PCB pocket and 44 mm female thread, with the base extended 6 mm below the floor to a flat bottom that holds the knob's insert |
| Hood + Thread + Baffle | `RENDER_HOOD` | 30 mm baffled shroud; the barrel end is a 31.7 mm band that takes a standard 1.25" eyepiece barrel cap |
| Dust Cap | `RENDER_CAP` | Printed slip-on cap for the band — a fallback if you have no spare eyepiece cap |

**Hardware:** one M4 × 20 star knob (Ø12.5 collar) from behind the mount into one M4 × 6 heat-set insert (5.9 mm knurl) in the center of the housing's bottom. Tightening it clamps the housing's flat bottom onto the seat. The insert pocket has a 45° lead-in and a narrower relief that catches displaced plastic and stops the insert flush.

**Cap:** use the cap from the bottom of any 1.25" eyepiece (or Barlow / diagonal) barrel — the caps for the eye-lens end vary in size and won't fit.

**Printing** (a single part exports in its print orientation):
- Mount, hood (lip-thread end down) and cap (closed top down): no supports.
- Base: bottom face on the bed — it is the clamping face, so it comes out flat. Needs supports at v2's two spots only (see [Print Settings](#print-settings)).

### Camera Housing v2 (`housing_v2.scad`) — recommended

Redesigned cylindrical housing with a **threaded connection** between the base and hood — no external screws, bolts, or tools needed. The hood hand-screws directly into the base.

Three parts controlled by `RENDER_*` flags:

| Part | Flag | Description |
|------|------|-------------|
| PCB Base + Lip + Dovetail | `RENDER_BASE` | Cylindrical 50 mm shell with internal 44 mm female thread, PCB pocket, and finder-shoe dovetail |
| Hood + Thread + Baffle | `RENDER_HOOD` | Matching male thread, stepped flange, baffled lens shroud |
| Dust Cap | `RENDER_CAP` | Friction-fit cap over the hood's lens opening |

**Improvements over v1:**
- No fasteners — hood screws onto the base by hand.
- Cylindrical outer shell.
- Coarse thread (44 mm × 3 mm pitch, 30° flank) — prints cleanly on FDM and gives a confident hand-tight grip.
- Back of the base has a chord-flat to shorten the USB plug tunnel.
- Upper PCB pocket has filleted corners so thread material never cantilevers over the pocket (no internal supports needed).

Uses [`vendor/threads.scad`](vendor/threads.scad) by Ryan Colyer (CC0) for the thread generation.

> **Thread fit:** `lip_thread_tolerance` (default 0.4 mm) sets the clearance between the male and female threads. If the hood binds on your printer, bump it to 0.5 mm; if it's sloppy, drop to 0.3 mm. Re-render base and hood STLs after changing.

To export a single part: set its flag to `true`, all others to `false`, then Render (F6) and export as STL.

### Camera Housing v1 (`housing.scad`) — legacy (bolted)

Complete enclosure for the 25mm UVC camera module with M12 lens. Contains three parts controlled by `RENDER_*` flags:

| Part | Flag | Description |
|------|------|-------------|
| PCB Base + Dovetail | `RENDER_BASE` | Holds camera PCB with integrated finder shoe rail |
| Hood + Baffle | `RENDER_HOOD` | Lens shroud with integral stepped light baffle |
| Dust Cap | `RENDER_CAP` | Friction-fit lens cap |

The base has two screw hole variants controlled by `SELF_TAP_SCREWS`:
- `true` (default) — 2.7mm holes for self-tapping screws
- `false` — 3.5mm clearance holes for M3 bolt-through with nuts

To export a single part: set its flag to `true`, all others to `false`, then Render (F6) and export as STL.

### Laser Pointer Holder (`laser_pointer_v2.scad`)

V-groove cradle for a 23mm-diameter laser pointer, mounted directly under a dovetail saddle that slides onto a standard telescope finder shoe. The saddle design is derived from [rziomber's Vixen-style dovetail](https://www.thingiverse.com/thing:4853379), adapted to the finder shoe profile used by the camera housing.

The cradle sits beneath the saddle with two 5 mm bridging side walls that leave the front and back of the cavity open — the laser pointer slides in along the Y axis and is held in place with cable ties through slots cut into the V-block floor and the bottom of the side walls.

A captive 1/4-20 hex nut pocket in the V-block floor lets the holder mount on a photography-tripod quick-release plate as an alternative to the finder shoe.

**Print orientation:** Lay the part on its side (XZ plane on the bed, Y axis vertical). This makes the captive-nut insertion slot a small bridge and the hex pocket vertices land at top/bottom, avoiding flat unsupported overhangs.

### M12 Lens Adapter (`lens_adapter.stl`)

Replacement M12 lens mount for cameras whose stock mount doesn't accept standard M12 threading. Square base with flanged mounting ears sits on the camera PCB; cylindrical tube provides an M12 bore.

### M12 Lock Ring (`lock_ring.stl`)

Lock ring that secures the M12 lens at the correct focus position. Features a tapered centering collar and grip notches for finger tightening.

### Camera Base (`camera_base.scad`) — spare part

Replacement for the white plastic base that ships under the 25 mm camera module's PCB, in case it breaks. Same 25 × 25 × 4.5 mm envelope, so the camera sits at the same height in the housing.

- **Four corner legs** support the PCB only on the bare 4.5 mm area around each mounting hole (21.3 mm spacing), keeping clear of the components on the underside.
- **Hot glue instead of screws** — a 2.2 mm channel runs from each PCB hole down through its leg and the floor into a recess on the underside. The glue sets as a hooked plug, so it holds even though hot glue bonds poorly to printed plastic, and it releases with heat or isopropyl alcohol.
- **USB-C cutout** — full-height notch centered on one edge for the socket on the PCB underside.

**Assembly:** place the base on baking paper, set the PCB on top with the holes aligned, and inject hot glue into each PCB hole until it leaves a small head on top. Once cool, peel off the paper and trim any glue standing proud of the underside.

**Print orientation:** floor down, no supports. PETG preferred; with PLA, use a low-temperature glue gun so the thin legs don't soften.

## Pre-built STLs

Ready-to-print STL files are in the [`stls/`](stls/) directory:

| File | Description |
|------|-------------|
| `housing_v3_mount.stl` | **v3** Dovetail mount with rotation seat |
| `housing_v3_base.stl` | **v3** PCB Base + Thread, flat clamping bottom |
| `housing_v3_hood.stl` | **v3** Hood with 1.25" cap band |
| `housing_v3_cap.stl`  | **v3** Fallback slip-on cap |
| `housing_v2_base.stl` | **v2** PCB Base + Thread + Dovetail |
| `housing_v2_hood.stl` | **v2** Hood + Male Thread + Baffle |
| `housing_v2_cap.stl`  | **v2** Dust Cap |
| `housing_base_selftap.stl` | v1 Base (2.7mm self-tap holes) |
| `housing_base_bolt.stl` | v1 Base (3.5mm bolt-through holes) |
| `housing_hood.stl` | v1 Hood + Baffle |
| `housing_cap.stl` | v1 Dust Cap |
| `laser_pointer_v2.stl` | Laser Pointer Holder (23 mm V-groove cradle + dovetail saddle) |
| `lens_adapter.stl` | M12 Lens Adapter |
| `lock_ring.stl` | M12 Lock Ring |
| `camera_base.stl` | Spare camera base (replaces the module's white base) |

## Print Settings

| Setting | Housing | Lens Adapter / Lock Ring |
|---------|---------|--------------------------|
| Layer height | 0.2mm | 0.2mm |
| Perimeters | 3 | 3 |
| Infill | 20% | 100% |
| Supports | Base only (see below) | None |

**Base supports.** The hood, cap and v3 mount are support-free, but the base needs slicer supports in two places:

- **USB cutout roof** (v1, v2 and v3) — the top edge of the USB slot is an unsupported span.
- **Upper edge of the chord-flat** (v2 and v3) — above `back_flat_y`, the back of the cylinder returns to its full diameter and overhangs the chord-flat below.

Most slicers (Cura, PrusaSlicer, OrcaSlicer, Bambu Studio) will place these automatically with "Supports on build plate only" or tree supports; custom support blockers aren't needed.

## Building Housing STLs from Source

Requires [OpenSCAD](https://openscad.org/) (command line or GUI).

### Command Line

```bash
# v3 (rotation) — each part alone is placed in its print orientation
for part in MOUNT BASE HOOD CAP; do
  args=""
  for p in MOUNT BASE HOOD CAP; do
    [ "$p" = "$part" ] && v=true || v=false
    args="$args -D RENDER_$p=$v"
  done
  openscad -o "stls/housing_v3_$(echo $part | tr A-Z a-z).stl" $args housing_v3.scad
done

# v2 (threaded) — recommended
openscad -o stls/housing_v2_base.stl \
  -D 'RENDER_BASE=true' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=false' housing_v2.scad
openscad -o stls/housing_v2_hood.stl \
  -D 'RENDER_BASE=false' -D 'RENDER_HOOD=true' -D 'RENDER_CAP=false' housing_v2.scad
openscad -o stls/housing_v2_cap.stl \
  -D 'RENDER_BASE=false' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=true' housing_v2.scad

# v1 (bolted) — base self-tapping variant
openscad -o stls/housing_base_selftap.stl \
  -D 'RENDER_BASE=true' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=false' \
  -D 'SELF_TAP_SCREWS=true' housing.scad

# v1 — base bolt-through variant
openscad -o stls/housing_base_bolt.stl \
  -D 'RENDER_BASE=true' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=false' \
  -D 'SELF_TAP_SCREWS=false' housing.scad

# v1 — Hood + Baffle
openscad -o stls/housing_hood.stl \
  -D 'RENDER_BASE=false' -D 'RENDER_HOOD=true' -D 'RENDER_CAP=false' housing.scad

# v1 — Cap
openscad -o stls/housing_cap.stl \
  -D 'RENDER_BASE=false' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=true' housing.scad
```
