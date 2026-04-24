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

use <vendor/threads.scad>

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
pocket_corner_radius  = 5;       // fillet on upper pocket corners — keeps the
                                 // corners inside the lip's thread root so no
                                 // thread material cantilevers over the pocket

/* Base enclosure */
base_floor_thickness  = 3+2;       // solid floor below the PCB pocket
base_pcb_depth        = 5;       // depth of the lower PCB pocket (below ledge)
base_upper_depth      = 5;       // clearance above PCB to top face
base_outer_dia        = 50;      // outer diameter of the cylindrical shell
base_corner_radius    = 6;       // minkowski rounding radius on corners (hood only)

/* Threaded lip — female thread on top of the base for a screw-on cap/hood */
lip_height            = 8;       // collar height above the base
lip_thread_dia        = 44;      // nominal female thread diameter
lip_thread_pitch      = 3;       // coarse pitch — FDM-friendly
lip_tooth_angle       = 30;      // half-angle of thread flank (30° = 60° included, metric)
lip_thread_tolerance  = 0.4;     // clearance for the mating male thread

/* USB cable cutout (rear face of base) */
usb_width             = 13;      // cutout width
usb_height            = 7;       // cutout height
usb_x_offset          = 8.5;     // horizontal offset from base origin
usb_z_offset          = base_floor_thickness - 1;       // vertical offset from base bottom
back_flat_y           = 18;      // chord-flat Y (all material at Y > this is removed
                                 // to shorten the USB tunnel; set to base_outer_dia/2
                                 // to keep the back fully cylindrical)
/* Screw holes — 4-corner pattern connecting base and hood */
screw_spacing         = 17;      // distance from body center to each hole
screw_tap_dia         = 2.7;     // self-tapping hole diameter (in base)
screw_clearance_dia   = 3.5;     // clearance hole diameter (in hood plate and bolt-through base)

/* Hood — cylindrical lens shroud, screws into the base's threaded lip */
hood_bore_dia         = 23;      // inner bore at tooth roots (clear_dia + 2×tooth_depth)
hood_wall_thickness   = 2.5;     // shroud wall thickness (above the step flange)
hood_length           = 44;      // height of the baffled shroud above the step flange
hood_step_height      = 5;       // plain flange between the thread and the narrower shroud
hood_flange_dia       = 36;      // flange OD — must be ≤ thread root dia (≈38.8 for
                                 // 44 mm × 3 mm pitch × 30° thread) so the flange sits
                                 // inside every thread valley with no overhang

/* Sawtooth baffle — concentric ring baffles on inner wall */
baffle_clear_dia      = 20;      // clear aperture at tooth tips
baffle_tooth_depth    = 1.5;     // radial depth of each tooth (inward protrusion)
baffle_tooth_pitch    = 3;       // axial distance between teeth
baffle_margin_bottom  = 3;       // smooth bore zone above the plate (lens clearance)
baffle_margin_top     = 3;       // smooth bore zone at the opening (cap fit area)

/* Dust cap */
cap_height            = 10;      // cap depth
cap_wall_thickness    = 2;       // cap wall thickness
cap_fit_clearance     = 0.2;     // friction-fit tolerance

/* Dovetail mounting rail — slides into telescope finder shoe */
dovetail_top_width    = 20;      // narrow end (bonds to mounting pad)
dovetail_bottom_width = 33;      // wide end (sits in finder shoe channel)
dovetail_height       = 11;      // trapezoid cross-section height (Y extent)
dovetail_length       = 39;      // rail length (Z extrusion)
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

// Hood — shroud OD (narrow section above the step flange)
hood_outer_dia   = hood_bore_dia + 2 * hood_wall_thickness;       // 28  — shroud OD

// Sawtooth baffle zone
baffle_zone      = hood_length - baffle_margin_bottom - baffle_margin_top;
baffle_n_teeth   = floor(baffle_zone / baffle_tooth_pitch);

// Cap
cap_inner_dia    = hood_outer_dia + cap_fit_clearance;            // slips over hood
cap_outer_dia    = cap_inner_dia + cap_wall_thickness * 2;

// Dovetail — Y offset so the mounting pad overlaps the base by dovetail_base_overlap
// Base outer edge in -Y = base_outer_dia / 2 (cylindrical shell).
// The pad top (closest to base) must reach that edge minus the overlap.
// In local coords, pad top is at dovetail_height - 1 + dovetail_pad_depth.
dovetail_y_offset = -(base_outer_dia / 2
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
            difference() {
                union() {
                    // Outer shell — cylindrical, centered at (0,0)
                    cylinder(d = base_outer_dia, h = base_height);

                    // Dovetail rail — on the -Y side, slides into finder shoe
                    translate([0, dovetail_y_offset, 0])
                        _dovetail_rail();
                }

                // Upper pocket — full PCB clearance zone (above floor),
                // bounded at the base top so the lip's thread stays intact.
                // Filleted corners fit inside the thread root so no thread
                // material cantilevers over the pocket.
                hull() {
                    for (x = [-body_width / 2 + pocket_corner_radius,
                               body_width / 2 - pocket_corner_radius])
                    for (y = [-body_width / 2 + pocket_corner_radius,
                               body_width / 2 - pocket_corner_radius])
                        translate([x, y, base_floor_thickness])
                            cylinder(r = pocket_corner_radius,
                                     h = base_height - base_floor_thickness);
                }

                // Lower ledge pocket — slightly smaller, PCB rests on the step
                translate([-inset_width / 2, -inset_width / 2,
                           base_floor_thickness - pcb_ledge_depth])
                    cube([inset_width, inset_width,
                          base_height - base_floor_thickness + pcb_ledge_depth]);

                // USB cable cutout — through the rear wall (+Y face)
                translate([usb_x_offset - body_width / 2,
                           body_width / 2 - 8, usb_z_offset - 0.5])
                    cube([usb_width, base_corner_radius * 2 + 10, usb_height]);
            }

            // Threaded lip — sits on top of the base
            translate([0, 0, base_height])
                _threaded_lip();
        }

        // Chord-flat on the back — shortens the USB tunnel. Runs from the
        // base bottom up to Z = base_height - 1, leaving a 1 mm full-circle
        // ring just below the lip and keeping the lip itself a full circle.
        translate([-base_outer_dia, back_flat_y, -1])
            cube([2 * base_outer_dia, base_outer_dia, base_height]);
    }
}


// --------------------------------------------------
// Threaded lip — female thread collar on top of the base
// --------------------------------------------------
// A solid annular collar matching the base's outer diameter,
// with a female thread cut through its interior. A mating
// cap or hood with a male thread of the same diameter/pitch
// screws onto it.

module _threaded_lip() {
    ScrewHole(outer_diam = lip_thread_dia,
              height = lip_height,
              pitch = lip_thread_pitch,
              tooth_angle = lip_tooth_angle,
              tolerance = lip_thread_tolerance)
        cylinder(d = base_outer_dia, h = lip_height);
}


// --------------------------------------------------
// Hood + Baffle
// --------------------------------------------------
// Hollow cylindrical lens shroud with a male thread at the
// bottom that screws into the base's female lip. No plate,
// no overhangs: the bore runs fully through from end to end
// so the part prints without supports in either orientation.
// Concentric sawtooth baffle rings on the inner wall of the
// shroud trap stray light; smooth margins at the bore ends
// provide lens clearance and cap fit.

module hood() {
    union() {
        // Male thread section — hollow threaded tube, bore passes through
        difference() {
            ScrewThread(outer_diam = lip_thread_dia,
                        height = lip_height,
                        pitch = lip_thread_pitch,
                        tooth_angle = lip_tooth_angle,
                        tolerance = lip_thread_tolerance);
            translate([0, 0, -1])
                cylinder(d = hood_bore_dia, h = lip_height + 2);
        }

        // Step flange — plain cylinder sized to fit inside the thread's root
        // diameter so it sits within every thread valley and prints without
        // overhanging the thread below
        translate([0, 0, lip_height])
            difference() {
                cylinder(d = hood_flange_dia, h = hood_step_height);
                translate([0, 0, -1])
                    cylinder(d = hood_bore_dia, h = hood_step_height + 2);
            }

        // Baffled shroud — narrower OD, bore continues at hood_bore_dia
        translate([0, 0, lip_height + hood_step_height])
            _hood_cylinder();
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
// Helper: hood cylinder with integrated sawtooth baffle
// --------------------------------------------------
// Single rotate_extrude of the full wall cross-section:
// outer wall, inner bore with sawtooth teeth, smooth margins
// at top and bottom. No boolean operations needed — the profile
// defines everything in one pass.
//
// Tooth orientation: flat blocking face at TOP (faces incoming
// light from the hood opening), ramp angled downward (deflects
// reflected light into the next tooth toward the wall).

module _hood_cylinder() {
    outer_r = hood_outer_dia / 2;
    bore_r  = hood_bore_dia / 2;
    tip_r   = baffle_clear_dia / 2;

    y_start = baffle_margin_bottom;
    y_end   = hood_length - baffle_margin_top;

    // Build polygon points tracing the wall cross-section clockwise:
    //   bottom-inner → up inner wall (with teeth) → top-inner →
    //   top-outer → down outer wall → bottom-outer
    tooth_points = [for (i = [0 : baffle_n_teeth - 1]) each [
        [bore_r, y_start + i * baffle_tooth_pitch],          // tooth root (flat face start)
        [tip_r,  y_start + (i + 1) * baffle_tooth_pitch],    // tooth tip (sharp edge, facing out)
    ]];

    points = concat(
        [[bore_r, 0]],                  // bottom inner
        [[bore_r, y_start]],            // start of baffle zone
        tooth_points,                   // sawtooth inner wall
        [[bore_r, y_end]],              // end of baffle zone
        [[bore_r, hood_length]],        // top inner
        [[outer_r, hood_length]],       // top outer
        [[outer_r, 0]]                  // bottom outer
    );

    rotate_extrude($fn = $fn)
        polygon(points);
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
    translate([0, 0, RENDER_BASE ? base_height + lip_height + preview_gap : 0])
        hood();

if (RENDER_CAP)
    translate([0, 0,
               (RENDER_BASE ? base_height + lip_height + preview_gap : 0)
               + (RENDER_HOOD ? lip_height + hood_step_height + hood_length
                                + preview_gap : 0)])
        cap();
