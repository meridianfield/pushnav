# PushNav 3D Models

3D-printable parts for the PushNav camera system. All models are written in [OpenSCAD](https://openscad.org/) for FDM printing. The hood, cap, and accessories print without supports; the base needs localised slicer supports (see [Print Settings](#print-settings)).

## Parts

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

### Laser Pointer Holder (`laser_pointer.scad`)

Dovetail saddle with snap-in clips for mounting a laser pointer on a standard telescope finder shoe. The saddle design is derived from [rziomber's Vixen-style dovetail](https://www.thingiverse.com/thing:4853379), adapted to the finder shoe profile used by the camera housing.

Two clip sizes for different laser pointers:

| Clip set | Laser diameter | Position |
|----------|---------------|----------|
| Large | 23mm (flashlight-style) | Left side of extension plate |
| Small | 14mm (pen-style) | Right side of extension plate |

Two 1/4-20 UNC tripod mount holes on the underside of the extension plate:

| Hole | Diameter | Usage |
|------|----------|-------|
| Tap hole | 5.1mm | Tap with 1/4-20 after printing |
| Insert hole | 8.9mm | Press in a 1/4-20 brass heat-set insert (OD ~9.5mm, 6.4mm length) |

**Print orientation:** XZ plane as base (on its side) for strong snap clips. Supports required for the overhanging clip.

### M12 Lens Adapter (`lens_adapter.stl`)

Replacement M12 lens mount for cameras whose stock mount doesn't accept standard M12 threading. Square base with flanged mounting ears sits on the camera PCB; cylindrical tube provides an M12 bore.

### M12 Lock Ring (`lock_ring.stl`)

Lock ring that secures the M12 lens at the correct focus position. Features a tapered centering collar and grip notches for finger tightening.

## Pre-built STLs

Ready-to-print STL files are in the [`stls/`](stls/) directory:

| File | Description |
|------|-------------|
| `housing_v2_base.stl` | **v2** PCB Base + Thread + Dovetail |
| `housing_v2_hood.stl` | **v2** Hood + Male Thread + Baffle |
| `housing_v2_cap.stl`  | **v2** Dust Cap |
| `housing_base_selftap.stl` | v1 Base (2.7mm self-tap holes) |
| `housing_base_bolt.stl` | v1 Base (3.5mm bolt-through holes) |
| `housing_hood.stl` | v1 Hood + Baffle |
| `housing_cap.stl` | v1 Dust Cap |
| `lens_adapter.stl` | M12 Lens Adapter |
| `lock_ring.stl` | M12 Lock Ring |

## Print Settings

| Setting | Housing | Lens Adapter / Lock Ring |
|---------|---------|--------------------------|
| Layer height | 0.2mm | 0.2mm |
| Perimeters | 3 | 3 |
| Infill | 20% | 100% |
| Supports | Base only (see below) | None |

**Base supports.** The hood and cap are support-free, but the base needs slicer supports in two places:

- **USB cutout roof** (v1 and v2) — the top edge of the USB slot is an unsupported span.
- **Upper edge of the chord-flat** (v2 only) — above `back_flat_y`, the back of the cylinder returns to its full diameter and overhangs the chord-flat below.

Most slicers (Cura, PrusaSlicer, OrcaSlicer, Bambu Studio) will place both automatically with "Supports on build plate only" or tree supports; custom support blockers aren't needed.

## Building Housing STLs from Source

Requires [OpenSCAD](https://openscad.org/) (command line or GUI).

### Command Line

```bash
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
