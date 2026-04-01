// Copyright (C) 2026 Arun Venkataswamy
//
// This file is part of PushNav.
//
// PushNav is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// PushNav is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with PushNav. If not, see <https://www.gnu.org/licenses/>.

// ============================================================
// PushNav Camera Housing
// ============================================================
//
// 3D-printable housing for a 25mm UVC camera module with M12 lens.
// Three separate parts bolt/friction-fit together:
//
//   1. PCB Base + Dovetail — holds the camera PCB with integrated finder shoe rail
//   2. Hood + Baffle       — screws onto the base, lens shroud with integral stepped baffle
//   3. Cap                 — friction-fit dust cap for the lens opening
//
// PRINTING:
//   To export an individual part for printing:
//     1. Set the part's RENDER_* flag to true, all others to false
//     2. Render (F6) and export as STL
//   To preview the full assembly, set all flags to true and preview (F5).
//
// All parts print without supports on any FDM printer.
// Recommended: 0.2mm layer height, 3 perimeters, 20% infill.


// ============================================================
// CONFIGURATION — toggle parts for STL export
// ============================================================

RENDER_BASE     = true;
RENDER_HOOD     = true;
RENDER_CAP      = true;

SELF_TAP_SCREWS = true;       // true  = self-tapping (smaller base holes)
                              // false = bolt-through (clearance holes in both base and hood)


// ============================================================
// DIMENSIONS — all values in millimeters
// ============================================================

/* Resolution */
$fn = 90;

/* Camera PCB */
pcb_width             = 25;      // camera module board width
pcb_clearance         = 5;       // extra room around PCB in pocket
pcb_ledge_inset       = 1;       // step-in from pocket wall for resting ledge
pcb_ledge_depth       = 1.5;     // vertical depth of the ledge step

/* Base enclosure */
base_floor_thickness  = 3;       // solid floor below the PCB pocket
base_pcb_depth        = 5;       // depth of the lower PCB pocket (below ledge)
base_upper_depth      = 5;       // clearance above PCB to top face
base_corner_radius    = 6;       // minkowski rounding radius on corners

/* USB cable cutout (rear face of base) */
usb_width             = 13;      // cutout width
usb_height            = 7;       // cutout height
usb_x_offset          = 8.5;     // horizontal offset from base origin
usb_z_offset          = 2;       // vertical offset from base bottom

/* Screw holes — 4-corner pattern connecting base and hood */
screw_spacing         = 17;      // distance from body center to each hole
screw_tap_dia         = 2.7;     // self-tapping hole diameter (in base)
screw_clearance_dia   = 3.5;     // clearance hole diameter (in hood plate and bolt-through base)

/* M12 lens */
lens_dia              = 18;      // M12 lens thread outer diameter

/* Baffle — stepped light baffle integrated into hood cylinder */
baffle_fov            = 11;      // camera field of view in degrees
baffle_num_steps      = 20;      // number of staircase steps (~2mm each)
baffle_min_wall       = 1.0;     // minimum wall thickness — steps stop expanding here

/* Hood — cylindrical lens shroud with integral stepped baffle */
hood_wall_thickness   = 2;       // cylinder wall thickness at lens end (thickest point)
hood_length           = 40;      // height of the hood cylinder
hood_plate_thickness  = 6;       // thickness of the mounting plate

/* Dust cap */
cap_height            = 15;      // cap depth
cap_wall_thickness    = 3;       // cap wall thickness
cap_fit_clearance     = 0.2;     // friction-fit tolerance

/* Dovetail mounting rail — slides into telescope finder shoe */
dovetail_top_width    = 20;      // narrow end (bonds to mounting pad)
dovetail_bottom_width = 33;      // wide end (sits in finder shoe channel)
dovetail_height       = 11;      // trapezoid cross-section height (Y extent)
dovetail_length       = 42;      // rail length (Z extrusion)
dovetail_pad_width    = 20;      // mounting pad width (X)
dovetail_pad_depth    = 10;      // mounting pad depth (Y, bridges rail to base)
dovetail_base_overlap = 2;       // how far the pad extends into base footprint


// ============================================================
// DERIVED VALUES — computed from dimensions above
// ============================================================

// Base enclosure
body_width       = pcb_width + pcb_clearance;                     // 30  — pocket inner width
inset_width      = pcb_width + pcb_ledge_inset;                   // 26  — ledge inner width
base_height      = base_floor_thickness + base_pcb_depth
                   + base_upper_depth;                            // 13  — total base box height

// Hood + baffle (single piece — baffle bore cut directly into hood cylinder)
hood_outer_dia   = lens_dia + 2 * hood_wall_thickness;            // 22  — hood cylinder OD
baffle_max_bore  = hood_outer_dia - 2 * baffle_min_wall;          // 20  — bore stops here (min wall)
baffle_top_dia   = lens_dia
                   + 2 * hood_length * tan(baffle_fov / 2);      // unclamped cone opening

// Cap
cap_inner_dia    = hood_outer_dia + cap_fit_clearance;            // slips over hood
cap_outer_dia    = cap_inner_dia + cap_wall_thickness * 2;

// Dovetail — Y offset so the mounting pad overlaps the base by dovetail_base_overlap
// Base outer edge in -Y = body_width/2 + base_corner_radius (minkowski expansion).
// The pad top (closest to base) must reach that edge minus the overlap.
// In local coords, pad top is at dovetail_height - 1 + dovetail_pad_depth.
dovetail_y_offset = -(body_width / 2 + base_corner_radius
                      - dovetail_base_overlap
                      + dovetail_pad_depth
                      + dovetail_height - 1);

// Preview spacing — vertical gap between parts in assembled preview
preview_gap      = 5;


// ============================================================
// MODULES
// ============================================================

// --------------------------------------------------
// PCB Base + Dovetail
// --------------------------------------------------
// Rounded-corner box with a stepped pocket for the camera PCB.
// The PCB sits on a shallow ledge. USB cable exits through a
// cutout on the rear face. Four screw holes on top for the hood.
// A dovetail mounting rail on the -Y side slides into a standard
// telescope finder shoe bracket.

module pcb_base() {
    difference() {
        union() {
            // Outer shell — rounded corners via minkowski sum, centered at (0,0)
            minkowski() {
                translate([-body_width / 2, -body_width / 2, 0])
                    cube([body_width, body_width, base_height / 2]);
                cylinder(r = base_corner_radius, h = base_height / 2);
            }

            // Dovetail rail — on the -Y side, slides into finder shoe
            translate([0, dovetail_y_offset, 0])
                _dovetail_rail();
        }

        // Upper pocket — full PCB clearance zone (above floor)
        translate([-body_width / 2, -body_width / 2, base_floor_thickness])
            cube([body_width, body_width, base_height]);

        // Lower ledge pocket — slightly smaller, PCB rests on the step
        translate([-inset_width / 2, -inset_width / 2,
                   base_floor_thickness - pcb_ledge_depth])
            cube([inset_width, inset_width, base_height]);

        // USB cable cutout — through the rear wall (+Y face)
        translate([usb_x_offset - body_width / 2,
                   body_width / 2, usb_z_offset])
            cube([usb_width, base_corner_radius * 2 + 10, usb_height]);

        // Screw holes — 4-corner pattern
        _screw_pattern(SELF_TAP_SCREWS ? screw_tap_dia : screw_clearance_dia,
                       base_height + base_corner_radius * 2);
    }
}


// --------------------------------------------------
// Hood + Baffle
// --------------------------------------------------
// Flat mounting plate that bolts onto the base, with a tall
// cylindrical lens shroud extending upward. The hood wall
// contains an integral stepped light baffle — a staircase
// approximation of the FOV cone that blocks stray light.
// The lens hole passes through the center of the plate.

module hood() {
    step_height = hood_length / baffle_num_steps;

    difference() {
        union() {
            // Mounting plate — same rounded footprint as the base, centered at (0,0)
            minkowski() {
                translate([-body_width / 2, -body_width / 2, 0])
                    cube([body_width, body_width, hood_plate_thickness / 2]);
                cylinder(r = base_corner_radius, h = hood_plate_thickness / 2);
            }

            // Hood cylinder — solid; the stepped baffle bore is cut below
            translate([0, 0, hood_plate_thickness])
                cylinder(d = hood_outer_dia, h = hood_length);
        }

        // Lens hole — through the plate
        translate([0, 0, -1])
            cylinder(d = lens_dia, h = hood_plate_thickness + 2);

        // Stepped baffle bore — staircase approximation of FOV cone.
        // Step 0 (bottom, at plate) has the narrowest bore (lens_dia).
        // Each step widens following the FOV cone, clamped to
        // baffle_max_bore so the wall never thins below baffle_min_wall.
        translate([0, 0, hood_plate_thickness])
            for (i = [0 : baffle_num_steps - 1]) {
                raw_dia = lens_dia
                          + (baffle_top_dia - lens_dia) * (i / baffle_num_steps);
                step_dia = min(raw_dia, baffle_max_bore);
                translate([0, 0, i * step_height - 0.01])
                    cylinder(d = step_dia, h = step_height + 0.02);
            }

        // Screw holes — clearance diameter, countersunk from below
        translate([0, 0, -base_corner_radius])
            _screw_pattern(screw_clearance_dia,
                           hood_plate_thickness + base_corner_radius * 2 + 10);
    }
}


// --------------------------------------------------
// Dust Cap
// --------------------------------------------------
// Friction-fit cap that slips over the top of the hood
// cylinder to protect the lens when not in use.

module cap() {
    difference() {
        cylinder(d = cap_outer_dia, h = cap_height);
        // Hollow interior — open at the bottom, closed at top
        translate([0, 0, -1])
            cylinder(d = cap_inner_dia, h = cap_height - cap_wall_thickness + 1);
    }
}


// --------------------------------------------------
// Helper: dovetail rail
// --------------------------------------------------
// Trapezoid-profile mounting rail integrated into the PCB base.
// Sits on the -Y side (opposite the USB cutout) and slides into
// a standard telescope finder shoe bracket. A rectangular
// mounting pad bridges the rail's narrow top to the base.
//
// Cross-section (looking from +Z, rail in -Y direction):
//
//    +Y  (USB side / base)
//     |
//     |  +---------+        <- mounting pad (bridges to base)
//     |  |         |
//     |   \       /         <- trapezoid (narrow top)
//     |    \     /
//     |     \   /
//     |      \_/            <- trapezoid (wide bottom, finder shoe)
//     |
//    -Y

module _dovetail_rail() {
    // Trapezoid rail — extruded vertically along Z.
    // Wide face (bottom_width) at Y=0, narrow face (top_width) at Y=height.
    linear_extrude(dovetail_length)
        polygon(points = [
            [-dovetail_bottom_width / 2, 0],
            [ dovetail_bottom_width / 2, 0],
            [ dovetail_top_width / 2, dovetail_height],
            [-dovetail_top_width / 2, dovetail_height]
        ]);

    // Mounting pad — rectangular bridge from rail top toward the base.
    // Starts 1mm below the trapezoid top for a solid overlap,
    // extends dovetail_pad_depth mm toward the base.
    translate([-dovetail_pad_width / 2, dovetail_height - 1, 0])
        cube([dovetail_pad_width, dovetail_pad_depth, base_height]);
}


// --------------------------------------------------
// Helper: screw hole pattern
// --------------------------------------------------
// Four holes in a square pattern centered on the body.
// Used by both base (tap dia) and hood (clearance dia).

module _screw_pattern(hole_dia, hole_depth) {
    for (x = [-screw_spacing, screw_spacing]) {
        for (y = [-screw_spacing, screw_spacing]) {
            translate([x, y, -1])
                cylinder(d = hole_dia, h = hole_depth + 2);
        }
    }
}


// ============================================================
// RENDER
// ============================================================
// Each part is centered at its own origin for individual STL export.
// In preview mode (all true), parts are stacked vertically with gaps
// so you can inspect the full assembly.

if (RENDER_BASE)
    pcb_base();

if (RENDER_HOOD)
    translate([0, 0, RENDER_BASE ? base_height + preview_gap : 0])
        hood();

if (RENDER_CAP)
    translate([0, 0,
               (RENDER_BASE ? base_height + preview_gap : 0)
               + (RENDER_HOOD ? hood_plate_thickness + hood_length + preview_gap : 0)])
        cap();
