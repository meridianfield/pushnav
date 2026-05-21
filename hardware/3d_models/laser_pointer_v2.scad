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
// PushNav Laser Pointer Holder v2
// ============================================================
//
// 3D-printable holder for a cylindrical laser pointer, designed
// to mount on a standard telescope finder shoe via a dovetail saddle.
//
// v2 changes from v1:
//   - V-groove block sits directly UNDER the saddle (no +X extension)
//   - V sized for an 18mm laser pointer (90° V, depth 22mm)
//   - 1/4-20 tripod mount holes removed (to be revisited)
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
//   1. Slide the laser pointer into the V-groove from the front or back.
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

/* V-groove laser pointer cradle — same V dimensions as v1.
   The V only cradles ~14mm of the cylinder; an 18mm laser pointer rests
   on the V walls but its top protrudes above the V opening (see
   laser_top_z below). The side walls + gap account for this. */
groove_depth        = 13;        // depth of V cut from block top (mm)
groove_width        = groove_depth * 2 * tan(45);    // 90° V: 26mm
groove_wall         = (saddle_size[0] - groove_width) / 2;  // 12mm each side
block_width         = saddle_size[0];                       // 50mm — matches saddle footprint
floor_thickness     = 10;        // solid material below V tip — bumped from v1's 8mm
                                 // to host the captive 1/4-20 nut pocket without
                                 // breaking through into the V cavity
block_height        = groove_depth + floor_thickness;  // 23mm
block_length        = saddle_size[1];                  // 46mm — matches saddle

/* Laser cylinder placement — derived from V geometry.
   In a 90° V, an r-radius cylinder rests with its center at r*sqrt(2)
   above the V tip and its top at r*(1+sqrt(2)) above the V tip. */
laser_diameter = 18;
laser_radius   = laser_diameter / 2;
laser_center_z = floor_thickness + laser_radius * sqrt(2);       // 20.73
laser_top_z    = floor_thickness + laser_radius * (1 + sqrt(2)); // 29.73

/* Stack — V-block on bottom, then side walls spanning (cylinder protrusion
   above V opening) + 5mm clearance, then the saddle. The two side walls
   bridge the gap on the +X and -X sides; the front and back of the gap
   stay open so the cylinder slides in from either Y end. */
gap_above_laser  = 5;                                // clear space above the cylinder top
saddle_z         = laser_top_z + gap_above_laser;    // 34.73
wall_thickness   = 5;                                // X width of each bridging side wall
side_wall_height = saddle_z - block_height;          // 13.73 (= laser protrusion + 5mm gap)
total_height     = saddle_z + saddle_size[2];        // 52.73

// Cable tie slots — open slots cut into the front and back faces of the block.
// Push the cable tie (or rubber band) straight in from the outside; no threading.
cable_tie_slot_w    = 9.5;       // slot depth into block (Y) — fits 3.6mm standard tie
cable_tie_slot_h    = 5;         // slot height (Z)

/* Side clamping screws (M5) — engage the finder shoe rail inside the
   dovetail channel. Same geometry as v1, positioned in the saddle. */
screw_diameter = 5;
nut_size       = [8.0, 4.7];    // M5 [across-flats, height]
screw_z        = saddle_z + 15; // mirrors v1's Z=15 within its 18mm saddle

/* Captive 1/4-20 hex nut pocket — for mounting on a photography tripod
   quick-release plate. Nut slides in from the -Y (front) face through a
   slot, then sits in a hex pocket in the V-block floor. A clearance hole
   from the bottom face lets the QR-plate screw thread up into the nut.
   Insertion is from Y so that, with the part printed lying on its side
   (XZ plane on the bed, Y axis vertical), the slot's ceiling is a tiny
   bridge instead of a wide unsupported overhang.
   Standard 1/4-20 hex nut: ~11.1mm across flats, ~5.6mm thick. */
// Clearances are generous because the slot/pocket are printed vertically
// (Y axis up) with supports — layer bulge and bridge sag eat into the
// nominal dimensions, so we oversize before printing.
tnut_af              = 11.1 + 0.6;   // 11.7mm — ~0.59mm clearance on flats
tnut_thickness       = 5.6 + 0.7;    // 6.3mm  — ~0.74mm clearance on Z
tnut_floor_below     = 1.5;          // retention floor between nut and bottom face
tnut_screw_clearance = 7.5;          // 1.15mm dia clearance for a 6.35mm screw
tnut_hex_r           = tnut_af / 2 / cos(30);   // circumscribed radius for $fn=6 hex
tnut_x               = block_width / 2;          // pocket centred in X
tnut_y               = block_length / 2;         // pocket centred in Y
tnut_z               = tnut_floor_below;         // pocket bottom in Z


// ============================================================
// MODULES
// ============================================================

module v_groove_block() {
    difference() {
        // Solid block at Z=0..block_height, full saddle footprint in X/Y
        cube([block_width, block_length, block_height]);

        // V-groove — 90° included angle, runs full block length in Y.
        // Tip points down into block, opening faces up.
        translate([block_width / 2, -1, block_height])
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
        translate([-1, -1, 0])
            cube([block_width + 2, cable_tie_slot_w + 1, cable_tie_slot_h]);
        // Back slot (open at Y=block_length)
        translate([-1, block_length - cable_tie_slot_w, 0])
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
        // V-groove cradle block — sits on the bed at Z=0..block_height
        v_groove_block();

        // Bridging side walls — span the gap between the V-block top and
        // the saddle bottom on the -X and +X sides only, leaving the
        // front/back of the gap open for the laser cylinder to slide in.
        translate([0, 0, block_height])
            cube([wall_thickness, block_length, side_wall_height]);
        translate([block_width - wall_thickness, 0, block_height])
            cube([wall_thickness, block_length, side_wall_height]);

        // Dovetail saddle — sits on top of the side walls
        translate([0, 0, saddle_z])
            cube(saddle_size, center = false);
    }

    // Dovetail channel — trapezoid matching housing.scad finder shoe rail.
    // Wide at bottom (deep in saddle), narrow at top (saddle surface).
    translate([saddle_size[0] / 2, -1, saddle_z + saddle_size[2]])
        rotate([-90, 0, 0])
            linear_extrude(saddle_size[1] + 2)
                polygon([
                    [-channel_top_width / 2, -1],
                    [ channel_top_width / 2, -1],
                    [ channel_bottom_width / 2, channel_depth],
                    [-channel_bottom_width / 2, channel_depth]
                ]);

    // Side clamping screws — enter from left wall, angled 15 deg downward
    translate([0, saddle_size[1] / 2 - 15, screw_z])
        rotate([0, 105, 0]) {
            cylinder(h = 40, r = screw_diameter / 2, center = true);
            translate([0, 0, 6])
                screw_insert();
        }

    translate([0, saddle_size[1] / 2 + 15, screw_z])
        rotate([0, 105, 0]) {
            cylinder(h = 40, r = screw_diameter / 2, center = true);
            translate([0, 0, 6])
                screw_insert();
        }

    // Top-edge cable tie slots — same shape as the V-block floor slots,
    // shifted up to the V-block top so they cut through the bottom of
    // the two side walls. The tie threads through one side wall, over
    // the laser pointer, and out through the other side wall, pulling
    // the pointer down into the V.
    // Front slot (open at Y=0)
    translate([-1, -1, block_height])
        cube([block_width + 2, cable_tie_slot_w + 1, cable_tie_slot_h]);
    // Back slot (open at Y=block_length)
    translate([-1, block_length - cable_tie_slot_w, block_height])
        cube([block_width + 2, cable_tie_slot_w + 1, cable_tie_slot_h]);

    // Captive 1/4-20 hex nut pocket — three cuts:
    //   (a) hex pocket centred at (tnut_x, tnut_y, tnut_z), rotated 30°
    //       so flats are perpendicular to the X axis (matching the slot
    //       walls) and vertices sit on +Y/-Y. With Y vertical at print
    //       time, the hex narrows to a point at top and bottom — no flat
    //       overhang to bridge.
    //   (b) rectangular insertion slot from the -Y (front) face into the
    //       pocket. Slot ceiling at Y=tnut_y is a ~11.4mm bridge that
    //       prints unsupported.
    //   (c) clearance hole from the bottom face up through the floor
    translate([tnut_x, tnut_y, tnut_z])
        rotate([0, 0, 30])
            cylinder($fn = 6, r = tnut_hex_r, h = tnut_thickness);
    translate([tnut_x - tnut_af / 2, -1, tnut_z])
        cube([tnut_af, tnut_y + 1, tnut_thickness]);
    translate([tnut_x, tnut_y, -1])
        cylinder(d = tnut_screw_clearance, h = floor_thickness + 2);
}

// ============================================================
// VISUALIZATION — temporary laser pointer cylinder (not part of the print)
// ============================================================
// The `%` modifier renders this as translucent grey for reference and
// excludes it from the actual geometry / STL export.
%translate([block_width / 2, -10, laser_center_z])
    rotate([-90, 0, 0])
        cylinder(d = laser_diameter, h = block_length + 20);
