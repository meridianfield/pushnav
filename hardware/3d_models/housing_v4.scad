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

use <housing_v3.scad>       // camera housing and hood, unchanged — preview only

// ============================================================
// PushNav Camera Housing v4 — Raspberry Pi 3A+ standalone unit
// ============================================================
//
// v3's camera on a taller mount, with a Raspberry Pi 3A+ in a slim box
// between the camera and the finder shoe. The camera parts — housing,
// hood and cap — are v3's, unchanged: print them from housing_v3.scad.
// This file adds the new mount and the box.
//
// Mount: v3's dovetail rail, seat and knob, with a 15 mm riser on the
// rail so the shoe's thumbscrews have room under the box, and a taller,
// stiffer stem that lifts the seat — and the camera — clear of the box.
// The camera's weight goes down the stem into the rail; the box only
// carries the Pi.
//
// Box: generated with YAPP_Box (vendor/YAPP_Box, MIT) — base and lid
// with a ridge and snap joins, the Pi on pins in the base, held down by
// pushers in the lid. It sits on the riser with its back against the
// stem, fixed by two screws from inside into inserts in the riser.
//
// Board orientation (standing behind the unit, at the eyepiece end):
//   USB-A faces forward, under the camera — the one side that is clear
//   on every scope · power (micro-USB) on the right · GPIO header on the
//   left · microSD at the back, against the stem (no slot — lift the lid
//   to change the card) · status LEDs seen through a window in the back
//   wall, right of the stem.
// YAPP names walls from its own top view: its LEFT wall (Y = 0) is the
// right side when standing behind the unit, and its RIGHT wall (Y max)
// the left.
//
//   1. Mount     — rail, riser, stem and seat
//   2. Box base  — YAPP base shell
//   3. Box lid   — YAPP lid shell with vent slots over the SoC
//
// HARDWARE:
//   v3's M4 × 20 star knob and M4 × 6 insert in the camera housing
//   2 × M4 × 4 heat-set inserts (5.8 mm knurl), pressed into the riser's top
//   2 × M4 × 6–10 pan or button head screws, from inside the box
//   For power, a right-angle micro-USB plug keeps within ~10 mm of the
//   side. The USB-A plug at the front must not turn upward, into the
//   camera's view.
//
// PRINTING:
//   To export one part, set its RENDER_* flag to true and the others to
//   false, then Render (F6) and export as STL. A single part is placed in
//   its print orientation:
//     - Mount: back face on the bed, as v3.
//     - Box base: floor on the bed.
//     - Box lid: top on the bed (YAPP lays it out beside the base).
//   No supports for any of the three.
// Recommended: 0.2mm layer height, 3 perimeters, 20% infill.


// ============================================================
// CONFIGURATION
// ============================================================

RENDER_MOUNT    = true;
RENDER_BOX_BASE = true;
RENDER_BOX_LID  = true;

// Preview only
SHOW_CAMERA             = true;  // v3's housing and hood, from housing_v3.scad —
                                 // the threads make previews slow; turn off
                                 // while working on the mount or the box
camera_preview_rotation = 0;     // housing turned on its seat (degrees)

/* Resolution */
$fn = 90;


// ============================================================
// RASPBERRY PI 3A+ — Raspberry Pi mechanical drawing RP-008330
// ============================================================
// Board coordinates (bx, by) follow the drawing's top view: bx along the
// 65 mm edge from the microSD edge, by along the 56 mm edge from the
// power edge. Values marked ~ are read from the drawing's outlines.
// With USB-A forward and power on the right, they are also YAPP's PCB
// coordinates — no flip. All of this must stay above the YAPP include
// (see vendor/README.md).

pi_length           = 65;
pi_width            = 56;
pi_thickness        = 1.4;
pi_hole_inset       = 3.5;            // hole centres from each edge
pi_usb_face_bx      = 68.2;           // ~ USB-A front face, past the board edge
pi_usb_by           = [24.8, 38.1];
pi_usb_height       = 7.3;            // 7.0 body + flange
pi_power_bx         = [6.7, 14.5];    // micro-USB, centre 10.6
pi_power_height     = 2.65;
pi_audio_overhang   = 2.5;            // ~ audio barrel past the power edge
pi_led_bx           = 1;              // ~ PWR / ACT LEDs at the microSD edge
pi_led_by           = [7.5, 12.5];
pi_sd_overhang      = 2.5;            // ~ seated card past the board edge
pi_sd_socket_bx     = [2, 13.5];      // underside
pi_soc_bx           = [20, 34];
pi_soc_by           = [24.4, 38.4];
pi_gpio_height      = 8.5;            // tallest part on top
pi_underside        = 1.8;            // GPIO pin tails; the microSD socket is 1.28


// ============================================================
// PI BOX — inputs to YAPP (own names, never YAPP's)
// ============================================================

box_wall            = 2;
box_floor           = 1.5;
box_roof            = 1.5;
box_round           = 3;
box_ridge           = 4;              // YAPP needs ≥ 1.8 × wall for snap joins
box_base_wall       = 8;              // base wall above the floor; the seam sits here
pi_standoff_height  = 4;              // floor → board underside: pin tails, SD socket,
                                      // and the box screws' heads under the board
pi_roof_clearance   = 9.5;            // board top → lid inside (GPIO header + 1)

// Padding from the board to the inside of each wall (YAPP names)
pi_pad_front        = pi_usb_face_bx - pi_length - box_wall;   // 1.2 — USB-A face flush outside
pi_pad_back         = 3;              // microSD edge — the seated card stands 2.5 proud
pi_pad_left         = 3;              // power edge (YAPP left, Y = 0) — audio barrel is 2.5 out
pi_pad_right        = 2;              // GPIO edge (YAPP right)

// Cutouts
usb_clearance       = 0.75;
power_opening       = [12, 8];        // along the wall × tall — room for the plug's moulding
led_window          = [7, 4];         // along the back wall × top above the board's top
vent_slots          = 5;              // lid slots over the SoC, running front to back
vent_slot_size      = [22, 3];        // length × width, round ends
vent_slot_pitch     = 5.5;
side_vents_x        = [24, 30, 36, 42];   // PCB X, GPIO wall, between the snaps
snap_width          = 12;


// ============================================================
// MOUNT
// ============================================================
// Same frame as v3: Z along the optical axis from the seat's back face,
// Y up, the optical axis at the origin.

/* From v3 — must match housing_v3.scad */
dovetail_top_width    = 20;      // narrow end (joins the riser)
dovetail_bottom_width = 33;      // wide end (sits in finder shoe channel)
dovetail_height       = 11;      // trapezoid cross-section height
dovetail_length       = 39;      // rail length, along the axis
seat_dia              = 30;      // clamping face the housing bottom rests on
seat_height           = 12.3;    // sized so the knob's 20 mm thread fills the insert
seat_column_dia       = 16;      // seat narrows to this around the knob hole
knob_hole_dia         = 4.5;     // M4 clearance through the seat
camera_dia            = 50;      // housing's outer diameter   (v3: base_outer_dia)
camera_base_extension = 6;       // bottom face → floor        (v3: base_extension)
camera_base_height    = 15;      // floor → lip                (v3: base_height)
camera_hood_length    = 43;      // hood thread start → mouth  (v3: hood_top)

/* New in v4 */
riser_height          = 15;      // rail top → box floor — finger room for the
                                 // shoe's thumbscrews under the box
stem_width            = 20;      // v3's rib: 10
stem_depth            = 10;      // along the axis; v3's rib: 8
camera_gap            = 5;       // box top → housing bottom: lets heat out of the
                                 // lid vent, and the housing turns without rubbing
box_stem_gap          = 2;       // box's back wall → stem's front face — room for
                                 // print tolerances and to lift the box out

/* Box screws — down through the box floor into M4 × 4 heat-set inserts in
   the riser's top, on its centreline. Modeled at the knurl OD with a 45°
   lead-in, as v3; the relief beyond stops the insert flush and takes
   screws up to M4 × 10. */
box_screws_bx         = [19, 29];   // board X — the back one just clear of the
                                    // microSD socket under the board, the front
                                    // one as close as two insert pockets allow
box_screw_hole_dia    = 4.5;
box_screw_head_dia    = 8;       // M4 pan head — clearance checks only
box_screw_head_height = 2.6;
riser_insert_dia      = 5.9;
riser_insert_lead_in  = 0.8;
riser_insert_depth    = 4.3;     // 4 mm insert + 0.3 mm
riser_relief_dia      = 5;
riser_relief_depth    = 5;


// ============================================================
// DERIVED VALUES
// ============================================================

// ---- box (YAPP coordinates: X from the back, Y from YAPP left, Z up) ----
box_length          = 2 * box_wall + pi_pad_back + pi_length + pi_pad_front;  // 73.2
box_width           = 2 * box_wall + pi_pad_left + pi_width + pi_pad_right;   // 65
box_lid_wall        = pi_roof_clearance + pi_standoff_height + pi_thickness
                      - box_base_wall;                                        // 6.9
box_height          = box_floor + box_base_wall + box_lid_wall + box_roof;    // 17.9
pcb_origin          = [box_wall + pi_pad_back, box_wall + pi_pad_left,
                       box_floor + pi_standoff_height];   // board's back-right underside

// Wall cutouts that would end just above the lid's lower edge start at the
// seam instead (the base's outer wall top), so no hairline of lid wall is
// left spanning their bottom. Heights from the board's top.
seam_from_pcb_top   = box_floor + box_base_wall - box_ridge
                      - (pcb_origin[2] + pi_thickness);               // -1.4
usb_cut_top         = pi_usb_height + usb_clearance;
usb_cut             = [(pi_usb_by[0] + pi_usb_by[1]) / 2,
                       (usb_cut_top + seam_from_pcb_top) / 2,
                       pi_usb_by[1] - pi_usb_by[0] + 2 * usb_clearance,
                       usb_cut_top - seam_from_pcb_top];
power_cut           = [(pi_power_bx[0] + pi_power_bx[1]) / 2, pi_power_height / 2];
led_cut             = [(pi_led_by[0] + pi_led_by[1]) / 2,
                       (led_window[1] + seam_from_pcb_top) / 2,
                       led_window[0], led_window[1] - seam_from_pcb_top];
soc_cut             = [(pi_soc_bx[0] + pi_soc_bx[1]) / 2,
                       (pi_soc_by[0] + pi_soc_by[1]) / 2];
box_screws_pcb_y    = box_width / 2 - pcb_origin[1];      // on the riser's centreline

// ---- mount (v3 frame) ----
box_floor_y         = -(camera_dia / 2 + camera_gap + box_height);   // -47.9
riser_bottom_y      = box_floor_y - riser_height;                    // -62.9 — rail top
rail_y              = riser_bottom_y - dovetail_height;              // -73.9 — shoe face
dovetail_axis_dist  = -rail_y;                                       // 73.9 (v3: 43)
box_z0              = stem_depth + box_stem_gap;                     // box's back face
box_screws_z        = [for (bx = box_screws_bx) box_z0 + pcb_origin[0] + bx];
riser_length        = max(box_screws_z) + riser_insert_dia / 2
                      + riser_insert_lead_in + 2;                    // 2 mm past the
                                                                     // front pocket
seat_taper_top      = seat_height - 1;                               // 11.3
seat_taper_bot      = seat_taper_top - (seat_dia - seat_column_dia) / 2;  // 4.3
camera_z            = seat_height + camera_base_extension;           // housing floor
hood_z              = camera_z + camera_base_height;                 // hood screwed home

assert(pi_pad_front >= 0.5,
       "USB-A face would sit outside the front wall");
assert(pi_pad_left >= pi_audio_overhang + 0.3,
       "audio jack barrel would hit the power-side wall");
assert(pi_pad_back >= pi_sd_overhang + 0.3,
       "microSD card would hit the back wall");
assert(pi_roof_clearance >= pi_gpio_height + 0.5,
       "GPIO header would reach the lid");
assert(pi_standoff_height >= max(pi_underside, box_screw_head_height) + 1,
       "board underside within 1 mm of the pin tails or the box screws' heads");
assert(min(box_screws_bx) - box_screw_head_dia / 2 >= pi_sd_socket_bx[1] + 0.5,
       "a box screw's head would sit under the microSD socket");
assert(box_base_wall >= box_ridge + 1.5,
       "base wall too short for the lid's ridge — the base would render narrower than the lid");
assert(stem_width <= dovetail_top_width,
       "stem wider than the riser it stands on");
assert(stem_depth > seat_taper_bot && stem_depth < seat_taper_top,
       "stem should end on the seat's taper");
assert(seat_dia / 2 < -(box_floor_y + box_height),
       "seat would reach down into the box");
assert(riser_insert_depth + riser_relief_depth <= riser_height - 2,
       "box screw pockets too deep for the riser");
assert(box_screws_bx[1] - box_screws_bx[0] >= riser_insert_dia + 2 * riser_insert_lead_in + 2,
       "box screw pockets less than 2 mm apart");
assert(dovetail_top_width / 2 >= riser_insert_dia / 2 + riser_insert_lead_in + 2,
       "riser's round end would leave less than 2 mm around the front pocket");


// ============================================================
// YAPP_Box
// ============================================================

include <vendor/YAPP_Box/YAPPgenerator_v3.scad>

// Everything below overrides a YAPP default, so it comes after the include.

printBaseShell      = RENDER_BOX_BASE;
printLidShell       = RENDER_BOX_LID;
showSideBySide      = false;          // preview: lid on the base (exports are always side by side)
showPCB             = false;          // no board drawn — keeps the preview light
showOrientation     = false;
previewQuality      = 12;             // 48 facets, same on screen and in the STL
renderQuality       = 12;

pcbLength           = pi_length;
pcbWidth            = pi_width;
pcbThickness        = pi_thickness;
standoffHeight      = pi_standoff_height;
standoffDiameter    = 6;
standoffPinDiameter = 2.4;            // Pi holes are 2.75
standoffHoleSlack   = 0.4;
pcb = [["Main", pcbLength, pcbWidth, 0, 0, pcbThickness, standoffHeight,
        standoffDiameter, standoffPinDiameter, standoffHoleSlack]];

// Pins in the base, pushers in the lid that hold the board down
pcbStands = [[pi_hole_inset, pi_hole_inset, yappAllCorners]];

paddingFront        = pi_pad_front;
paddingBack         = pi_pad_back;
paddingLeft         = pi_pad_left;
paddingRight        = pi_pad_right;
wallThickness       = box_wall;
basePlaneThickness  = box_floor;
lidPlaneThickness   = box_roof;
baseWallHeight      = box_base_wall;
lidWallHeight       = box_lid_wall;
ridgeHeight         = box_ridge;
ridgeSlack          = 0.2;
roundRadius         = box_round;

// Box X from the back. The power opening on YAPP's left wall sits at
// X ≈ 10–22, so that wall's first snap moves back to 28.
snapJoins = [[8,  snap_width, yappRight],
             [28, snap_width, yappLeft],
             [56, snap_width, yappLeft, yappRight]];

// Cutouts — PCB coordinates; on the walls the height is from the board's top
cutoutsFront = [[usb_cut[0], usb_cut[1], usb_cut[2], usb_cut[3], 0,
                 yappRectangle, yappCenter]];
cutoutsLeft  = [[power_cut[0], power_cut[1], power_opening[0], power_opening[1], 0,
                 yappRectangle, yappCenter]];
cutoutsRight = [for (x = side_vents_x) [x, 4.5, 3, 5, 1, yappRoundedRect, yappCenter]];
cutoutsBack  = [[led_cut[0], led_cut[1], led_cut[2], led_cut[3], 0,
                 yappRectangle, yappCenter]];
cutoutsLid   = [for (k = [0 : vent_slots - 1])
                [soc_cut[0], soc_cut[1] + (k - (vent_slots - 1) / 2) * vent_slot_pitch,
                 vent_slot_size[0], vent_slot_size[1], 1, yappRoundedRect, yappCenter]];
cutoutsBase  = [for (bx = box_screws_bx) [bx, box_screws_pcb_y, 0, 0,
                 box_screw_hole_dia / 2, yappCircle, yappCenter]];


// ============================================================
// MODULES
// ============================================================

// --------------------------------------------------
// Mount — rail, riser, stem and seat
// --------------------------------------------------
// v3's rail and seat, pushed apart by the riser, the box and the camera
// gap. The riser stops 2 mm past the front box screw's pocket, in a
// semicircle; it is no wider than the rail's top, so the shoe's
// thumbscrews stay clear. The stem rises from the riser behind the box
// to the seat. Prints back face down, no supports — the round end is
// the top of the print.

module mount() {
    difference() {
        union() {
            // Rail — v3's dovetail profile
            translate([0, rail_y, 0])
                linear_extrude(dovetail_length)
                    polygon([[-dovetail_bottom_width / 2, 0],
                             [ dovetail_bottom_width / 2, 0],
                             [ dovetail_top_width / 2, dovetail_height],
                             [-dovetail_top_width / 2, dovetail_height]]);

            // Riser — the box floor rests on its top; round front end
            translate([0, box_floor_y, 0]) rotate([90, 0, 0])
                linear_extrude(riser_height + 0.01)
                    hull() {
                        translate([-dovetail_top_width / 2, 0])
                            square([dovetail_top_width,
                                    riser_length - dovetail_top_width / 2]);
                        translate([0, riser_length - dovetail_top_width / 2])
                            circle(d = dovetail_top_width);
                    }

            // Stem — from the riser, behind the box, up to the seat
            translate([-stem_width / 2, box_floor_y - 0.01, 0])
                cube([stem_width, -box_floor_y + 0.01, stem_depth]);

            // Seat — v3's: column around the knob, 45° taper (prints
            // unsupported), full diameter at the clamping face
            cylinder(d = seat_column_dia, h = seat_taper_bot + 0.01);
            translate([0, 0, seat_taper_bot])
                cylinder(d1 = seat_column_dia, d2 = seat_dia,
                         h = seat_taper_top - seat_taper_bot + 0.01);
            translate([0, 0, seat_taper_top])
                cylinder(d = seat_dia, h = seat_height - seat_taper_top);
        }

        // Knob hole
        translate([0, 0, -1])
            cylinder(d = knob_hole_dia, h = seat_height + 2);

        // Box screw inserts, down from the riser's top
        for (z = box_screws_z)
            translate([0, box_floor_y, z]) rotate([90, 0, 0])
                _riser_insert_pocket();
    }
}


// --------------------------------------------------
// Helper: heat-set insert pocket in the riser
// --------------------------------------------------
// Along +Z from its mouth at Z = 0: lead-in funnel, insert pocket, then
// the narrower relief that stops the insert flush and takes the screw.

module _riser_insert_pocket() {
    translate([0, 0, -1])
        cylinder(d = riser_insert_dia + 2 * riser_insert_lead_in, h = 1.01);
    cylinder(d1 = riser_insert_dia + 2 * riser_insert_lead_in, d2 = riser_insert_dia,
             h = riser_insert_lead_in);
    translate([0, 0, -1])
        cylinder(d = riser_insert_dia, h = riser_insert_depth + 1);
    translate([0, 0, -1])
        cylinder(d = riser_relief_dia, h = riser_insert_depth + riser_relief_depth + 1);
}


// --------------------------------------------------
// Box placement — YAPP coordinates → mount frame
// --------------------------------------------------
// Box X (back → front) runs along the axis from the stem, box Y (YAPP
// left → right) across from the observer's right, box Z up from the
// riser's top.

module _box_on_mount() {
    multmatrix([[0, 1, 0, -box_width / 2],
                [0, 0, 1, box_floor_y],
                [1, 0, 0, box_z0],
                [0, 0, 0, 1]])
        children();
}


// ============================================================
// RENDER
// ============================================================
// One part enabled → placed in its print orientation for export.
// Otherwise the unit is shown assembled (F5): mount, box on the riser,
// and v3's camera on the seat. In a full Render (F6) YAPP lays the lid
// out beside the base instead.

single_part = (RENDER_MOUNT ? 1 : 0) + (RENDER_BOX_BASE ? 1 : 0)
            + (RENDER_BOX_LID ? 1 : 0) == 1;

if (single_part) {
    if (RENDER_MOUNT) mount();
    else YAPPgenerate();
} else {
    if (RENDER_MOUNT) mount();
    if (RENDER_BOX_BASE || RENDER_BOX_LID)
        _box_on_mount() YAPPgenerate();
    if ($preview && SHOW_CAMERA)
        color("dimgray") rotate([0, 0, camera_preview_rotation]) {
            translate([0, 0, camera_z]) pcb_base();
            translate([0, 0, hood_z]) hood();
        }
}
