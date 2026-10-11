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
// PushNav Camera Base — replacement for the module's white base
// ============================================================
//
// Spare part for the 25 mm USB camera module (e.g. Waveshare OV9281):
// replaces the white plastic base that ships screwed under the PCB.
// Same 25 × 25 × 4.5 mm envelope, so the camera sits at the same
// height in the housing's PCB pocket.
//
// The PCB rests on four corner legs, each confined to the bare area
// around a mounting hole, leaving the underside components clear.
// Instead of tiny screws, the PCB is fixed with hot glue: a channel
// runs from each PCB hole down through its leg and the floor into a
// recess on the underside that points toward the center. The glue
// sets as a hooked plug through PCB, leg and floor, so it holds
// mechanically even though hot glue bonds poorly to printed plastic.
// It releases with gentle heat or isopropyl alcohol if the camera
// ever has to come out.
//
// ASSEMBLY:
//   1. Put the base on baking paper, PCB on top, holes aligned.
//   2. Inject hot glue into each PCB hole until it fills the channel
//      and leaves a small head on top of the PCB.
//   3. Let it cool, peel off the paper, trim any glue proud of the
//      underside so the base sits flat.
//
// PRINTING:
//   Floor down, no supports. PETG preferred; with PLA use a
//   low-temperature glue gun so the thin legs don't soften.


// ============================================================
// DIMENSIONS — all values in millimeters
// ============================================================

/* Resolution */
$fn = 64;

/* Outline */
base_size             = 25;      // square, matches the PCB
base_corner_radius    = 2.5;     // outline corner rounding
base_height           = 4.5;     // total height, floor to PCB underside
floor_thickness       = 1.2;     // leaves base_height - floor_thickness clear under the PCB

/* Legs — one per PCB mounting hole */
hole_spacing          = 21.3;    // PCB mounting hole centers (square pattern)
leg_dia               = 4.5;     // component-free area around each hole (PCB underside)

/* Hot-glue anchor */
glue_channel_dia      = 2.2;     // through each leg and the floor, under the PCB hole
glue_foot_width       = 2.2;     // recess on the underside, from the channel toward center
glue_foot_length      = 4;       // measured from the channel center
glue_foot_depth       = 0.8;     // into the floor from the underside

/* USB-C cutout — socket on the PCB underside, centered on the +Y edge */
usb_cutout_width      = 10.5;    // USB-C receptacle ≈ 8.9 mm + clearance
usb_cutout_depth      = 9;       // socket extends 8.5 mm in from the edge + 0.5


// ============================================================
// DERIVED VALUES
// ============================================================

hole_offset      = hole_spacing / 2;                          // 10.65
edge_wall        = base_size / 2 - hole_offset - glue_channel_dia / 2;
leg_height       = base_height - floor_thickness;             // 3.3

assert(edge_wall >= 0.6,
       "glue channel leaves less than 0.6 mm wall to the outer edge");
assert(glue_foot_depth < floor_thickness - 0.2,
       "glue foot recess leaves less than 0.2 mm of floor above it");
assert(usb_cutout_width / 2 < hole_offset - leg_dia / 2,
       "USB cutout would cut into the +Y legs");


// ============================================================
// MODULES
// ============================================================

module _outline(h) {
    r = base_corner_radius;
    hull()
        for (x = [-1, 1] * (base_size / 2 - r))
        for (y = [-1, 1] * (base_size / 2 - r))
            translate([x, y, 0])
                cylinder(r = r, h = h);
}

module _at_holes() {
    for (x = [-1, 1] * hole_offset)
    for (y = [-1, 1] * hole_offset)
        translate([x, y, 0])
            children();
}

module camera_base() {
    difference() {
        union() {
            _outline(floor_thickness);

            // Legs — the clear circle around each hole, trimmed to the outline
            intersection() {
                _outline(base_height);
                _at_holes()
                    cylinder(d = leg_dia, h = base_height);
            }
        }

        // Glue channel — through leg and floor
        _at_holes()
            translate([0, 0, -1])
                cylinder(d = glue_channel_dia, h = base_height + 2);

        // Glue foot — underside recess from the channel toward the center,
        // hooks the glue plug under the floor
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * hole_offset, sy * hole_offset, -1])
                rotate([0, 0, atan2(-sy, -sx)])
                    hull() {
                        cylinder(d = glue_foot_width, h = glue_foot_depth + 1);
                        translate([glue_foot_length - glue_foot_width / 2, 0, 0])
                            cylinder(d = glue_foot_width, h = glue_foot_depth + 1);
                    }

        // USB-C cutout — full height, centered on the +Y edge
        translate([-usb_cutout_width / 2, base_size / 2 - usb_cutout_depth, -1])
            cube([usb_cutout_width, usb_cutout_depth + 1, base_height + 2]);
    }
}


// ============================================================
// RENDER
// ============================================================

camera_base();
