---
layout: default
title: 3D Models
nav_order: 5
---

# 3D-Printable Parts

![3D Model](assets/3d_model.png)

All parts are designed in [OpenSCAD](https://openscad.org/) for FDM printing without supports. Source files are in [`hardware/3d_models/`](https://github.com/meridianfield/pushnav/tree/main/hardware/3d_models).

---

## Camera Housing

Complete enclosure for the camera module with M12 lens. Three parts designed to bolt and friction-fit together.

### PCB Base + Dovetail Rail

Holds the camera PCB with screw standoffs. Integrated dovetail rail slides into a standard telescope finder shoe. USB cable exits through a rear slot.

Two screw hole variants are available:

| Variant | Hole Size | Use |
|---------|-----------|-----|
| Self-tapping | 2.7mm | Self-tapping screws bite directly into plastic |
| Bolt-through | 3.5mm | M3 bolts pass through, secured with nuts |

{% raw %}
<p><a href="https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_base_selftap.stl" class="btn btn-primary">Download Base (self-tap)</a></p>
<p><a href="https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_base_bolt.stl" class="btn btn-primary">Download Base (bolt-through)</a></p>
{% endraw %}

### Hood + Baffle

Cylindrical lens shroud with an integral stepped light baffle. The baffle is a staircase approximation of the camera's field-of-view cone that blocks stray light while preserving the full FOV. Screws onto the base via the mounting plate.

{% raw %}
<div class="d-flex flex-wrap gap-4">
  <a href="https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_hood.stl" class="btn btn-primary">Download Hood</a>
</div>
{% endraw %}

### Dust Cap

Friction-fit cap that protects the lens when not in use. Slips over the hood cylinder.

{% raw %}
<div class="d-flex flex-wrap gap-4">
  <a href="https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_cap.stl" class="btn btn-primary">Download Cap</a>
</div>
{% endraw %}

---

## Lens Accessories

### M12 Lock Ring

Lock ring that secures the M12 lens at the correct focus position. Features a tapered centering collar and grip notches for finger tightening.

{% raw %}
<div class="d-flex flex-wrap gap-4">
  <a href="https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/lock_ring.stl" class="btn btn-primary">Download Lock Ring</a>
</div>
{% endraw %}

---

## Print Settings

| Setting | Housing | Lock Ring |
|---------|---------|-----------|
| Material | PLA or PETG | PLA or PETG |
| Layer height | 0.2mm | 0.12mm |
| Infill | 20% | 100% |
| Supports | None | None |

{: .note }
The lock ring should be printed at 100% infill and 0.12mm layer height for thread strength and a smooth finish. Use opaque filament for the housing to prevent stray light leaking through the walls.

---

## All Downloads

| File | Description |
|------|-------------|
| [`housing_base_selftap.stl`](https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_base_selftap.stl) | PCB Base + Dovetail (2.7mm self-tap holes) |
| [`housing_base_bolt.stl`](https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_base_bolt.stl) | PCB Base + Dovetail (3.5mm bolt-through holes) |
| [`housing_hood.stl`](https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_hood.stl) | Hood + Baffle |
| [`housing_cap.stl`](https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/housing_cap.stl) | Dust Cap |
| [`lock_ring.stl`](https://github.com/meridianfield/pushnav/raw/main/hardware/3d_models/stls/lock_ring.stl) | M12 Lock Ring |
