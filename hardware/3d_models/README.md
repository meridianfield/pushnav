# PushNav 3D Models

3D-printable parts for the PushNav camera system. All models are written in [OpenSCAD](https://openscad.org/) and designed for FDM printing without supports.

## Parts

### Camera Housing (`housing.scad`)

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
| `housing_base_selftap.stl` | PCB Base + Dovetail (2.7mm self-tap holes) |
| `housing_base_bolt.stl` | PCB Base + Dovetail (3.5mm bolt-through holes) |
| `housing_hood.stl` | Hood + Baffle |
| `housing_cap.stl` | Dust Cap |
| `lens_adapter.stl` | M12 Lens Adapter |
| `lock_ring.stl` | M12 Lock Ring |

## Print Settings

| Setting | Housing | Lens Adapter / Lock Ring |
|---------|---------|--------------------------|
| Layer height | 0.2mm | 0.2mm |
| Perimeters | 3 | 3 |
| Infill | 20% | 100% |
| Supports | None | None |

## Building Housing STLs from Source

Requires [OpenSCAD](https://openscad.org/) (command line or GUI).

### Command Line

```bash
# Base — self-tapping variant
openscad -o stls/housing_base_selftap.stl \
  -D 'RENDER_BASE=true' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=false' \
  -D 'SELF_TAP_SCREWS=true' housing.scad

# Base — bolt-through variant
openscad -o stls/housing_base_bolt.stl \
  -D 'RENDER_BASE=true' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=false' \
  -D 'SELF_TAP_SCREWS=false' housing.scad

# Hood + Baffle
openscad -o stls/housing_hood.stl \
  -D 'RENDER_BASE=false' -D 'RENDER_HOOD=true' -D 'RENDER_CAP=false' housing.scad

# Cap
openscad -o stls/housing_cap.stl \
  -D 'RENDER_BASE=false' -D 'RENDER_HOOD=false' -D 'RENDER_CAP=true' housing.scad
```
