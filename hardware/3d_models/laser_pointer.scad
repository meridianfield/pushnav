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
//   All parts print without supports on any FDM printer.
//   Recommended: 0.2mm layer height, 3 perimeters, 20% infill.



// ============================================================
// DIMENSIONS — all values in millimeters
// ============================================================

$fn = 200;

/* Saddle body — sized for finder shoe dovetail */
saddle_size = [50, 46, 18];     // [width, length, height]


/* Dovetail channel — matches housing.scad finder shoe rail + clearance */
channel_clearance    = 0.5;                            // per side
channel_bottom_width = 33 + 2 * channel_clearance;     // 34mm (wide, deep in saddle)
channel_top_width    = 20 + 2 * channel_clearance;     // 21mm (narrow, at saddle surface)
channel_depth        = 11 + channel_clearance;          // 11.5mm

/* Extension plate — chassis for snap-in laser pointer mount */
extension_length = 70;                                  // extends in +X from saddle
plate_thickness  = saddle_size[2] - channel_depth;      // matches saddle floor


/* Snap-in laser pointer clips */
laser_dia        = 23;          // large laser pointer barrel diameter
laser_dia_sm     = 14;          // small laser pointer barrel diameter
clip_clearance   = 0.5;         // bore diameter clearance (0.25mm per side)
clip_wall        = 4;           // wall thickness (outer side only, bore unchanged)
clip_open_half   = 67;          // half of opening angle (degrees)
clip_arm_h       = 5;           // arm/guide height above arc end
clip_depth       = 8;           // extrusion depth per clip
clip_front_y     = 0;                                   // flush with front edge
clip_back_y      = saddle_size[1] - clip_depth;          // flush with back edge
clip_margin      = 5;                                    // margin from plate edges
clip_gap         = 6;                                    // gap between clip sets

/* Derived clip values — large (23mm) */
clip_bore_r  = (laser_dia + clip_clearance) / 2;         // 11.75mm
clip_outer_r = clip_bore_r + clip_wall;                   // 14.75mm
clip_x       = saddle_size[0] + clip_margin + clip_outer_r;
clip_z       = plate_thickness + clip_bore_r;

/* Derived clip values — small (14mm) */
clip_bore_r_sm  = (laser_dia_sm + clip_clearance) / 2;   // 7.25mm
clip_outer_r_sm = clip_bore_r_sm + clip_wall;             // 10.25mm
clip_x_sm       = clip_x + clip_outer_r + clip_gap + clip_outer_r_sm;
clip_z_sm       = plate_thickness + clip_bore_r_sm;

/* 1/4-20 UNC tripod mount holes */
tripod_tap_dia    = 5.1;         // #7 drill for tapping 1/4-20 UNC
tripod_insert_dia = 8.9;         // pilot hole for 1/4-20 heat-set insert (OD ~9.5mm)
tripod_y          = saddle_size[1] / 2;
tripod_x_tap      = clip_x;                              // tap hole under large clips
tripod_x_insert   = clip_x + 10;                          // insert hole, 10mm to the right

/* Side clamping screws (M5) */
screw_diameter = 5;
nut_size       = [8.0, 4.7];    // M5 [across-flats, height]


// ============================================================
// MODULES
// ============================================================

// --------------------------------------------------
// Snap-in clip profile (2D)
// --------------------------------------------------
// C-shaped cradle (220 deg arc) with two straight guide arms.
// The bore circle is subtracted from the solid outer boundary.
//
// The profile sits in the XY plane with the bore center at the
// origin. Extrude along Z and rotate into position.

module snap_profile_2d(bore_r, outer_r) {
    n_arc = 60;     // arc point resolution

    a_right   = 90 - clip_open_half;                     // 20 deg
    arc_sweep = 360 - 2 * clip_open_half;                // 220 deg

    ro_x  = outer_r * cos(a_right);
    ro_y  = outer_r * sin(a_right);
    ri_x  = bore_r * cos(a_right);
    ri_y  = bore_r * sin(a_right);
    top_y = ro_y + clip_arm_h;

    difference() {
        polygon(concat(
            // Right arm: outer top → outer arc end
            [[ro_x, top_y], [ro_x, ro_y]],
            // Outer arc (right → CW through bottom → left)
            [for (i = [0:n_arc]) let(a = a_right - i * arc_sweep / n_arc)
                [outer_r * cos(a), outer_r * sin(a)]],
            // Left arm: outer arc end → outer top
            [[-ro_x, top_y]],
            // Left arm flat top (outer → inner)
            [[-ri_x, top_y]],
            // Left arm: inner top → inner arc end
            [[-ri_x, ri_y]],
            // Bridge across gap to right side
            [[ri_x, ri_y]],
            // Right arm: inner arc end → inner top
            [[ri_x, top_y]]
            // Close: right arm flat top back to start
        ));

        // Subtract bore
        circle(r = bore_r);
    }
}


module screw_insert() {
    // Hex nut pocket with insertion slot toward -X
    // https://www.engineersedge.com/hardware/standard_metric_hex_nuts_13728.htm
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

// Rotated for XZ-plane printing — Y=0 face becomes the print bed.
// Clip layers run along the arm length for maximum strength.
rotate([90, 0, 0])
difference() {
    union() {
        cube(saddle_size, center = false);

        // Extension plate — flat chassis for laser pointer mount
        translate([saddle_size[0], 0, 0])
            cube([extension_length, saddle_size[1], plate_thickness]);

        // Large clips (23mm)
        translate([clip_x, clip_front_y + clip_depth, clip_z])
            rotate([90, 0, 0])
                linear_extrude(clip_depth)
                    snap_profile_2d(clip_bore_r, clip_outer_r);

        translate([clip_x, clip_back_y + clip_depth, clip_z])
            rotate([90, 0, 0])
                linear_extrude(clip_depth)
                    snap_profile_2d(clip_bore_r, clip_outer_r);

        // Small clips (14mm)
        translate([clip_x_sm, clip_front_y + clip_depth, clip_z_sm])
            rotate([90, 0, 0])
                linear_extrude(clip_depth)
                    snap_profile_2d(clip_bore_r_sm, clip_outer_r_sm);

        translate([clip_x_sm, clip_back_y + clip_depth, clip_z_sm])
            rotate([90, 0, 0])
                linear_extrude(clip_depth)
                    snap_profile_2d(clip_bore_r_sm, clip_outer_r_sm);
    }

    // Dovetail channel — trapezoid matching housing.scad finder shoe rail.
    // Wide at bottom (deep in saddle), narrow at top (saddle surface).
    // Bar slides in from the end along Y.
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

    // 1/4-20 UNC tripod mount — tap hole (through)
    translate([tripod_x_tap, tripod_y, -1])
        cylinder(d = tripod_tap_dia, h = plate_thickness + 2);

    // 1/4-20 UNC tripod mount — heat-set insert hole (through)
    translate([tripod_x_insert, tripod_y, -1])
        cylinder(d = tripod_insert_dia, h = plate_thickness + 2);
}
