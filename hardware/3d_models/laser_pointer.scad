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
// PushNav Laser Pointer Holder
// ============================================================
//
// 3D-printable holder for a cylindrical laser pointer, designed
// to mount on a standard telescope finder shoe via a dovetail saddle.
//
// The saddle design is derived from:
//   "Vixen style dovetail bar and saddle (for telescope mount)"
//   by rziomber — https://www.thingiverse.com/thing:4853379
//
// PRINTING:
//   Print flat in XY orientation (default, Z=0 face on bed).
//   No supports required. 0.2mm layer height, 3 perimeters, 20% infill.
//
// ASSEMBLY:
//   1. Place the laser pointer in the V-groove cradle.
//   2. Push a cable tie (or rubber band) into the front slot, bring it
//      up both sides of the block, over the laser pointer, and click shut.
//   3. Repeat for the back slot.
//   4. Slide the dovetail saddle onto the finder shoe rail.


// ============================================================
// DIMENSIONS — all values in millimeters
// ============================================================

$fn = 200;

/* Saddle body — sized for finder shoe dovetail */
saddle_size = [50, 46, 18];     // [width, length, height]

/* Dovetail channel — matches housing.scad finder shoe rail + clearance */
channel_clearance    = 0.5;
channel_bottom_width = 33 + 2 * channel_clearance;
channel_top_width    = 20 + 2 * channel_clearance;
channel_depth        = 11 + channel_clearance;

/* Extension plate — base for the V-groove cradle */
plate_thickness  = saddle_size[2] - channel_depth;   // matches saddle floor

/* V-groove laser pointer cradle */
groove_depth        = 13;        // depth of V cut from block top (mm)
groove_width        = groove_depth * 2 * tan(45);    // 90° V: 26mm
groove_wall         = 5;         // side wall thickness on each side of V
block_width         = groove_width + 2 * groove_wall;  // 36mm
floor_thickness     = 8;         // solid material below V tip
block_height        = groove_depth + floor_thickness;  // 21mm
tie_clearance       = 8;             // gap between saddle and block for zip tie routing
extension_length    = tie_clearance + block_width;   // plate ends flush with the block
block_x             = saddle_size[0] + tie_clearance;
block_length        = saddle_size[1];

// Cable tie slots — open slots cut into the front and back faces of the block.
// Push the cable tie (or rubber band) straight in from the outside; no threading.
cable_tie_slot_w    = 9.5;       // slot depth into block (Y) — fits 3.6mm standard tie
cable_tie_slot_h    = 5;         // slot height (Z)

/* 1/4-20 UNC tripod mount holes — all centred on Y, spread across X.
   Depths vary per hole to keep all holes blind (see tripod_*_depth).
   Insert/T-nut: 12mm — 6.5mm plate + 5.5mm into block floor, adequate for
   heat-set inserts (8-12mm) and T-nuts (7-9mm).
   Tap: 8mm — limited by dovetail channel wall at X=40. */
tripod_tap_dia    = 5.1;         // #7 drill size for tapping 1/4-20 UNC
tripod_insert_dia = 8.9;         // pilot hole for heat-set insert (OD ~9.5mm)
tripod_tnut_dia   = 6.0;         // barrel hole for 1/4-20 T-nut
/* Per-hole depths — kept blind (no break-through).
   Tap hole (X=40) sits inside the dovetail channel footprint; the channel
   wall at X=40 reaches Z≈10mm, so depth is limited to 8mm to stay blind.
   Insert (X=50) and T-nut (X=60) are outside the channel; 12mm is safe. */
tripod_tap_depth    = 8;         // limited by dovetail channel wall at X=40
tripod_insert_depth = 12;        // safe: X=50 outside channel, 18mm material
tripod_tnut_depth   = 12;        // safe: X=60 under block, 27.5mm material
tripod_spacing    = 15;          // X spacing between holes
tripod_y          = saddle_size[1] / 2;                              // all holes centred on Y
tripod_x_center   = saddle_size[0];          // centre of base plate
tripod_x_tap      = tripod_x_center - tripod_spacing;               // left
tripod_x_insert   = tripod_x_center;                                // centre
tripod_x_tnut     = tripod_x_center + tripod_spacing;               // right

/* Side clamping screws (M5) */
screw_diameter = 5;
nut_size       = [8.0, 4.7];    // M5 [across-flats, height]


// ============================================================
// MODULES
// ============================================================

module v_groove_block() {
    difference() {
        // Solid block sitting on top of extension plate
        translate([block_x, 0, plate_thickness])
            cube([block_width, block_length, block_height]);

        // V-groove — 90° included angle, runs full block length in Y.
        // Tip points down into block, opening faces up.
        translate([block_x + block_width / 2, -1, plate_thickness + block_height])
            rotate([-90, 0, 0])
                linear_extrude(block_length + 2)
                    polygon([
                        [-groove_width / 2, 0],
                        [ groove_width / 2, 0],
                        [0, groove_depth]
                    ]);

        // Cable tie slots — open to front and back faces.
        // Push tie / rubber band straight in; no threading required.
        // Front slot (open at Y=0)
        translate([block_x - 1, -1, plate_thickness])
            cube([block_width + 2, cable_tie_slot_w + 1, cable_tie_slot_h]);
        // Back slot (open at Y=block_length)
        translate([block_x - 1, block_length - cable_tie_slot_w, plate_thickness])
            cube([block_width + 2, cable_tie_slot_w + 1, cable_tie_slot_h]);
    }
}


module screw_insert() {
    // Hex nut pocket with insertion slot toward -X
    hull() {
        linear_extrude(height = nut_size[1], twist = 0, center = false)
            regular_polygon(6, nut_size[0] / 2 / cos(360 / (6 * 2)));
        translate([-30, -nut_size[0] / 2, 0])
            cube([nut_size[0], nut_size[0], nut_size[1]], center = false);
    }
}

module regular_polygon(order = 4, r = 1) {
    angles = [for (i = [0 : order - 1]) i * (360 / order)];
    coords = [for (th = angles) [r * cos(th), r * sin(th)]];
    polygon(coords);
}


// ============================================================
// RENDER
// ============================================================

difference() {
    union() {
        // Dovetail saddle
        cube(saddle_size, center = false);

        // Extension plate — flat chassis for laser pointer cradle
        translate([saddle_size[0], 0, 0])
            cube([extension_length, saddle_size[1], plate_thickness]);

        // V-groove cradle block with cable tie channels
        v_groove_block();
    }

    // Dovetail channel — trapezoid matching housing.scad finder shoe rail.
    // Wide at bottom (deep in saddle), narrow at top (saddle surface).
    translate([saddle_size[0] / 2, -1, saddle_size[2]])
        rotate([-90, 0, 0])
            linear_extrude(saddle_size[1] + 2)
                polygon([
                    [-channel_top_width / 2, -1],
                    [ channel_top_width / 2, -1],
                    [ channel_bottom_width / 2, channel_depth],
                    [-channel_bottom_width / 2, channel_depth]
                ]);

    // Side clamping screws — enter from left wall, angled 15 deg downward
    translate([0, saddle_size[1] / 2 - 15, 15])
        rotate([0, 105, 0]) {
            cylinder(h = 40, r = screw_diameter / 2, center = true);
            translate([0, 0, 6])
                screw_insert();
        }

    translate([0, saddle_size[1] / 2 + 15, 15])
        rotate([0, 105, 0]) {
            cylinder(h = 40, r = screw_diameter / 2, center = true);
            translate([0, 0, 6])
                screw_insert();
        }

    // 1/4-20 UNC tripod mount holes — centred on Y, spread across X.
    // Tap hole (X=40, 8mm): within channel footprint — depth limited to stay blind.
    // Insert hole (X=50, 12mm): press in a heat-set insert from below.
    // T-nut hole (X=60, 12mm): barrel hole for a T-nut installed from below.
    translate([tripod_x_tap,    tripod_y, -1]) cylinder(d = tripod_tap_dia,    h = tripod_tap_depth    + 1);
    translate([tripod_x_insert, tripod_y, -1]) cylinder(d = tripod_insert_dia, h = tripod_insert_depth + 1);
    translate([tripod_x_tnut,   tripod_y, -1]) cylinder(d = tripod_tnut_dia,   h = tripod_tnut_depth   + 1);
}
