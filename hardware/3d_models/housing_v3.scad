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
// PushNav Camera Housing v3 — rotation adjustment
// ============================================================
//
// 3D-printable housing for a 25mm UVC camera module with M12 lens.
// Same housing, hood and cap as v2, but the dovetail is a separate
// mount and the housing can be turned about the optical axis, so the
// camera's up/down and left/right line up with the telescope's even
// when the finder shoe sits at an angle. Loosen the knob behind the
// mount, turn the camera, tighten.
//
//   1. Mount          — finder-shoe rail, bridge and round seat
//   2. PCB Base       — camera housing; a spigot underneath turns in the
//                       seat's socket and takes the knob's insert
//   3. Hood + Baffle  — screws onto the base, lens shroud with integral stepped
//                       baffle; its barrel end takes a standard 1.25" eyepiece
//                       barrel cap
//   4. Cap            — printed slip-on cap, a fallback for the eyepiece cap
//
// HARDWARE:
//   1 × M4 × 20 star knob (Ø12.5 collar), 1 × M4 × 6 heat-set insert
//   (5.9 mm knurl) in the spigot.
//
// PRINTING:
//   To export an individual part, set its RENDER_* flag to true and all
//   others to false — a single part is placed in its print orientation —
//   then Render (F6) and export as STL.
//     - Mount: back face on the bed, no supports.
//     - Base: spigot on the bed. Supports under the floor around the
//       spigot, plus v2's two spots (USB cutout roof, upper edge of the
//       chord-flat). The spigot's end face — the clamping face — is the
//       first layer, so it comes out flat.
//     - Hood: lip-thread end on the bed, no supports.
//     - Cap: closed top on the bed, no supports.
// Recommended: 0.2mm layer height, 3 perimeters, 20% infill.


// ============================================================
// CONFIGURATION — toggle parts for STL export
// ============================================================

RENDER_MOUNT    = true;
RENDER_BASE     = true;
RENDER_HOOD     = true;
RENDER_CAP      = true;

// Preview only
explode               = 10;      // gap between parts along the optical axis
base_preview_rotation = 0;       // housing turned on its seat (degrees)


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
base_floor_thickness  = 3+2;     // solid floor below the PCB pocket
base_pcb_depth        = 5;       // depth of the lower PCB pocket (below ledge)
base_upper_depth      = 5;       // clearance above PCB to top face
base_outer_dia        = 50;      // outer diameter of the cylindrical shell
base_corner_radius    = 6;       // sizes the USB cutout's run through the wall

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

/* Hood — cylindrical lens shroud, screws into the base's threaded lip */
hood_bore_dia         = 23;      // inner bore at tooth roots (clear_dia + 2×tooth_depth)
hood_wall_thickness   = 2.5;     // shroud wall thickness (above the step flange)
hood_length           = 30;      // height of the baffled shroud above the step flange —
                                 // blocks direct light from beyond ~30° off-axis and is
                                 // still ≥ 2× the lens aperture as a dew shield
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

/* Dust cap — the hood's barrel end is a 1.25" eyepiece-barrel band, so the
   cap from the bottom of any 1.25" eyepiece (or Barlow / diagonal) slips
   over it. A 45° step from the barrel up to the band prints without a
   ledge. The printed cap below is a fallback for anyone without a spare. */
cap_band_dia          = 31.7;    // 1.25" barrel = 31.75; printed ODs run slightly large
cap_band_len          = 12;      // band length at the barrel end
cap_wall_thickness    = 2;       // printed cap wall
cap_fit_clearance     = 0.2;     // printed cap friction fit over the band

/* Dovetail mounting rail — slides into telescope finder shoe */
dovetail_top_width    = 20;      // narrow end (joins the bridge)
dovetail_bottom_width = 33;      // wide end (sits in finder shoe channel)
dovetail_height       = 11;      // trapezoid cross-section height (Y extent)
dovetail_length       = 39;      // rail length (Z extrusion)
dovetail_axis_dist    = 43;      // optical axis → rail's wide (shoe) face, as v2

/* Rotation joint — the housing's spigot turns in a socket in the mount's
   seat. An M4 × 20 star knob from behind the mount runs through the seat
   floor into an insert in the spigot and clamps the spigot's end face
   onto the socket floor. That face is printed on the bed, so it is flat;
   the housing floor (printed over supports) clears the seat rim. */
knob_collar_dia       = 12.5;    // star knob bearing face
knob_thread_len       = 20;      // M4 thread under the collar
spigot_dia            = 20;      // under the housing floor, centers the rotation
spigot_height         = 6;
socket_clearance      = 0.5;     // diametral — printed holes run small, so this
                                 // keeps the turn free
rim_clearance         = 0.5;     // housing floor above the seat rim
seat_dia              = 30;      // socket wall around the spigot
seat_floor            = 12.3;    // seat material under the socket — sized so the
                                 // 20 mm thread fills the insert without bottoming
bridge_width          = 10;      // rib from the rail to the seat (X)
bridge_height         = 8;       // rib height from the back face; ties the seat's
                                 // column and lower taper to the rail
seat_column_dia       = 16;      // seat narrows to this around the knob hole, below
                                 // a 45° taper up to the full seat_dia

/* Heat-set insert pocket in the spigot — M4 × 6, 5.9 mm knurl OD. Modeled
   at the knurl OD (FDM holes print ~0.2–0.3 mm under) with a 45° lead-in;
   a narrower relief beyond catches displaced plastic and stops the insert
   flush with the spigot face. */
insert_hole_dia       = 5.9;
insert_lead_in        = 0.8;
insert_hole_depth     = 6.3;     // 6 mm insert + 0.3 mm
insert_relief_dia     = 5;
insert_relief_depth   = 2;
knob_hole_dia         = 4.5;     // M4 clearance through the seat floor


// ============================================================
// DERIVED VALUES — computed from dimensions above
// ============================================================

// Base enclosure
body_width       = pcb_width + pcb_clearance;                     // 30  — pocket inner width
inset_width      = pcb_width + pcb_ledge_inset;                   // 26  — ledge inner width
base_height      = base_floor_thickness + base_pcb_depth
                   + base_upper_depth;                            // 15  — total base box height

// Hood — shroud OD (narrow section above the step flange)
hood_outer_dia   = hood_bore_dia + 2 * hood_wall_thickness;       // 28  — shroud OD

// Sawtooth baffle zone
baffle_zone      = hood_length - baffle_margin_bottom - baffle_margin_top;
baffle_n_teeth   = floor(baffle_zone / baffle_tooth_pitch);

// Cap band and printed cap
cap_step_height  = (cap_band_dia - hood_outer_dia) / 2;           // 1.85 — 45° step
cap_inner_dia    = cap_band_dia + cap_fit_clearance;              // slips over the band
cap_outer_dia    = cap_inner_dia + 2 * cap_wall_thickness;
cap_height       = cap_band_len - 1 + cap_wall_thickness;         // stops on the barrel end
hood_top         = lip_height + hood_step_height + hood_length;   // 43

// Dovetail — Y of the rail's wide face and narrow (inner) face
dovetail_y_offset = -dovetail_axis_dist;                          // -43
rail_inner_y     = dovetail_y_offset + dovetail_height;           // -32

// Rotation joint
socket_depth     = spigot_height - rim_clearance;                 // 5.5
seat_height      = seat_floor + socket_depth;                     // 17.8 — seat rim Z
housing_z        = seat_floor + spigot_height;                    // 18.3 — housing floor Z
knob_tip         = knob_thread_len - seat_floor;                  // 7.7 — from spigot face
seat_taper_top   = seat_floor - 1;                                // 11.3 — full seat_dia from here up
seat_taper_bot   = seat_taper_top - (seat_dia - seat_column_dia) / 2;  // 4.3

assert(knob_tip >= insert_hole_depth - 0.3,
       "knob thread would not reach through the whole insert");
assert(knob_tip < insert_hole_depth + insert_relief_depth,
       "knob tip would bottom out past the insert relief");
assert(insert_hole_depth + insert_relief_depth
           <= spigot_height + base_floor_thickness - pcb_ledge_depth - 1,
       "insert pocket would come within 1 mm of the PCB pocket");
assert(seat_dia / 2 < back_flat_y,
       "seat rim would extend past the housing's back flat");
assert(seat_column_dia >= knob_collar_dia + 2,
       "knob collar too large for the seat column's back face");
assert(bridge_height > seat_taper_bot && bridge_height < seat_taper_top,
       "bridge rib should end on the seat's taper");
assert(seat_taper_top <= seat_floor - 1,
       "seat taper must reach the full diameter at least 1 mm below the socket floor");
assert(base_outer_dia / 2 < -rail_inner_y - 1,
       "housing would come within 1 mm of the rail");

// Preview spacing — vertical gap between parts in assembled preview
preview_gap      = 5;

// One part enabled → it is placed in its print orientation for export
single_part = (RENDER_MOUNT ? 1 : 0) + (RENDER_BASE ? 1 : 0)
            + (RENDER_HOOD ? 1 : 0) + (RENDER_CAP ? 1 : 0) == 1;


// ============================================================
// MODULES
// ============================================================

// --------------------------------------------------
// Mount — dovetail rail, bridge and seat
// --------------------------------------------------
// The rail sits where it was on v2. A low rib joins its narrow face to
// the round seat on the optical axis; the seat's socket takes the
// housing's spigot, which bottoms on the socket floor. The star knob
// goes in from the back face (Z = 0). Prints back face down, no supports.

module mount() {
    difference() {
        union() {
            translate([0, dovetail_y_offset, 0])
                _dovetail_rail();

            // Bridge — a low rib from the rail to the seat
            translate([-bridge_width / 2, rail_inner_y - 1, 0])
                cube([bridge_width, -rail_inner_y + 1, bridge_height]);

            // Seat — column around the knob, 45° taper (prints unsupported),
            // full diameter under the socket and rim
            cylinder(d = seat_column_dia, h = seat_taper_bot + 0.01);
            translate([0, 0, seat_taper_bot])
                cylinder(d1 = seat_column_dia, d2 = seat_dia,
                         h = seat_taper_top - seat_taper_bot + 0.01);
            translate([0, 0, seat_taper_top])
                cylinder(d = seat_dia, h = seat_height - seat_taper_top);
        }

        // Socket for the spigot
        translate([0, 0, seat_floor])
            cylinder(d = spigot_dia + socket_clearance, h = socket_depth + 1);

        // Knob hole
        translate([0, 0, -1])
            cylinder(d = knob_hole_dia, h = seat_floor + 2);
    }
}


// --------------------------------------------------
// PCB Base
// --------------------------------------------------
// Cylindrical shell with a stepped pocket for the camera PCB. The PCB
// sits on a shallow ledge. USB cable exits through a cutout on the rear
// face. A spigot under the floor turns in the mount's socket and holds
// the knob's insert.

module pcb_base() {
    difference() {
        union() {
            difference() {
                // Outer shell — cylindrical, centered at (0,0)
                cylinder(d = base_outer_dia, h = base_height);

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

            // Spigot — under the floor
            translate([0, 0, -spigot_height])
                cylinder(d = spigot_dia, h = spigot_height + 0.01);
        }

        // Chord-flat on the back — shortens the USB tunnel. Runs from the
        // base bottom up to Z = base_height - 1, leaving a 1 mm full-circle
        // ring just below the lip and keeping the lip itself a full circle.
        translate([-base_outer_dia, back_flat_y, -1])
            cube([2 * base_outer_dia, base_outer_dia, base_height]);

        // Insert pocket — from the spigot face
        translate([0, 0, -spigot_height])
            _insert_pocket();
    }
}


// --------------------------------------------------
// Helper: heat-set insert pocket
// --------------------------------------------------
// Along +Z from its mouth at Z = 0: lead-in funnel, insert pocket,
// then the narrower relief that stops the insert flush.

module _insert_pocket() {
    translate([0, 0, -1])
        cylinder(d = insert_hole_dia + 2 * insert_lead_in, h = 1.01);
    cylinder(d1 = insert_hole_dia + 2 * insert_lead_in, d2 = insert_hole_dia,
             h = insert_lead_in);
    translate([0, 0, -1])
        cylinder(d = insert_hole_dia, h = insert_hole_depth + 1);
    translate([0, 0, -1])
        cylinder(d = insert_relief_dia, h = insert_hole_depth + insert_relief_depth + 1);
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

        // 1.25" cap band on the barrel end, with its 45° step below
        translate([0, 0, hood_top - cap_band_len - cap_step_height])
            difference() {
                union() {
                    cylinder(d1 = hood_outer_dia, d2 = cap_band_dia,
                             h = cap_step_height + 0.01);
                    translate([0, 0, cap_step_height])
                        cylinder(d = cap_band_dia, h = cap_band_len);
                }
                translate([0, 0, -1])
                    cylinder(d = hood_outer_dia - 1,
                             h = cap_step_height + cap_band_len + 2);
            }
    }
}


// --------------------------------------------------
// Dust Cap
// --------------------------------------------------
// Fallback friction-fit cap for the hood's 1.25" band, for anyone
// without a spare eyepiece barrel cap. Open at the bottom, closed at
// the top; it stops on the barrel end.

module cap() {
    difference() {
        cylinder(d = cap_outer_dia, h = cap_height);
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
// Trapezoid-profile mounting rail. Sits on the -Y side (opposite
// the USB cutout at 0° rotation) and slides into a standard
// telescope finder shoe bracket.
//
// Cross-section (looking from +Z, rail in -Y direction):
//
//    +Y  (bridge / camera)
//     |
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
}


// ============================================================
// RENDER
// ============================================================
// With one part enabled it is placed in its print orientation for STL
// export; otherwise the assembly is shown along the optical axis,
// pulled apart by `explode`.

base_z = housing_z + explode;
hood_z = base_z + base_height + lip_height + preview_gap;
cap_z  = hood_z + hood_top + preview_gap;

if (single_part) {
    if (RENDER_MOUNT) mount();
    if (RENDER_BASE)
        translate([0, 0, spigot_height]) pcb_base();
    if (RENDER_HOOD) hood();
    if (RENDER_CAP)
        translate([0, 0, cap_height]) rotate([180, 0, 0])
            cap();
} else {
    if (RENDER_MOUNT) mount();

    rotate([0, 0, base_preview_rotation]) {
        if (RENDER_BASE) translate([0, 0, base_z]) pcb_base();
        if (RENDER_HOOD) translate([0, 0, hood_z]) hood();
        if (RENDER_CAP)  translate([0, 0, cap_z])  cap();
    }
}
