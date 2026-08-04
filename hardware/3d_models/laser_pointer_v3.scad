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
// PushNav Laser Pointer Holder v3
// ============================================================
//
// 3D-printable holder for a cylindrical laser pointer, designed
// to mount on a standard telescope finder shoe via a dovetail saddle.
//
// v3 changes from v2:
//   - Replaced the captive 1/4-20 hex nut + Y-face insertion slot
//     with a single heat-set brass insert bore in the bottom face
//     (8mm OD × 8mm insert, 7.8mm bore for melt-in interference fit).
//     No support material, no bridged slot ceiling, no orientation
//     constraint at print time. Any screw matching the insert's
//     internal thread can now mount the holder on a tripod QR plate.
//   - Dovetail clamp: the captive M5 hex-nut pockets are gone too —
//     two M4 brass heat-set inserts (5.8mm OD × 4mm) sit in the
//     saddle's -X outer wall instead. M4 matches commercial finder
//     shoe clamp screws. Both outer flanks are cut parallel to the
//     dovetail channel walls (uniform 6mm thickness, symmetric
//     trapezoid profile), so the inserts seat flush in the sloped
//     face and the clamp screws meet the rail's flank square-on.
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
//   5. Tighten the two M4 clamp screws (threaded into the heat-set
//      inserts in the sloped side wall) to lock the saddle on the rail.


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

/* V-groove laser pointer cradle — sized for a 23mm laser pointer.
   90° V with depth 15mm gives a 30mm opening, leaving ~3.5mm of slack
   on each side of a 23mm cylinder. The V only cradles part of the
   cylinder; the rest protrudes above the V opening (see laser_top_z
   below) and the side walls + gap account for this. */
groove_depth        = 15;        // depth of V cut from block top (mm) — bumped
                                 // from v1's 13mm to give a 23mm laser pointer
                                 // ~3.5mm of slack per side at the opening
groove_width        = groove_depth * 2 * tan(45);    // 90° V: 30mm
groove_wall         = (saddle_size[0] - groove_width) / 2;  // 10mm each side
block_width         = saddle_size[0];                       // 50mm — matches saddle footprint
floor_thickness     = 10;        // solid material below V tip — hosts the
                                 // 8mm-deep heat-set insert bore with ~1.5mm
                                 // of retention floor above it before the V cavity
block_height        = groove_depth + floor_thickness;  // 25mm
block_length        = saddle_size[1];                  // 46mm — matches saddle

/* Laser cylinder placement — derived from V geometry.
   In a 90° V, an r-radius cylinder rests with its center at r*sqrt(2)
   above the V tip and its top at r*(1+sqrt(2)) above the V tip. */
laser_diameter = 23;
laser_radius   = laser_diameter / 2;
laser_center_z = floor_thickness + laser_radius * sqrt(2);       // 26.26
laser_top_z    = floor_thickness + laser_radius * (1 + sqrt(2)); // 37.77

/* Stack — V-block on bottom, then side walls spanning (cylinder protrusion
   above V opening) + 5mm clearance, then the saddle. The two side walls
   bridge the gap on the +X and -X sides; the front and back of the gap
   stay open so the cylinder slides in from either Y end. */
gap_above_laser  = 5;                                // clear space above the cylinder top
saddle_z         = laser_top_z + gap_above_laser;    // 42.77
wall_thickness   = 5;                                // X width of each bridging side wall
side_wall_height = saddle_z - block_height;          // 17.77 (= laser protrusion + 5mm gap)
total_height     = saddle_z + saddle_size[2];        // 60.77

// Cable tie slots — open slots cut into the front and back faces of the block.
// Push the cable tie (or rubber band) straight in from the outside; no threading.
cable_tie_slot_w    = 9.5;       // slot depth into block (Y) — fits 3.6mm standard tie
cable_tie_slot_h    = 5;         // slot height (Z)

/* Side clamp — two M4 screws thread into brass heat-set inserts in the
   saddle's -X outer wall and press square onto the finder shoe rail's
   dovetail flank. M4 is the commercial norm for finder-shoe clamp
   screws; the smaller insert also lets the screw axis sit higher on
   the rail flank than an M5 insert would allow.
   Insert: M4 thread, 5.8mm knurled OD, 4mm long. */
dovetail_angle     = atan(((channel_bottom_width - channel_top_width) / 2)
                          / channel_depth);   // 29.5° from vertical
clamp_wall_t       = 6;                       // wall thickness ⊥ to channel wall
clamp_insert_od    = 5.8;
clamp_insert_len   = 4.0;
clamp_insert_bore  = clamp_insert_od - 0.4;   // 5.4mm — melt-in interference fit
clamp_insert_depth = clamp_insert_len + 0.5;  // 4.5mm — flush seat + relief
clamp_screw_clear  = 4.5;                     // M4 clearance bore behind the insert
clamp_bite_frac    = 0.4;                     // screw-tip contact height on the rail
                                              // flank: 0 = channel bottom, 1 = top.
                                              // 0.4 is as high as the insert bore can
                                              // sit while keeping ~1.8mm of material
                                              // to the saddle's top edge.

/* Sloped outer wall planes — the channel walls pushed outward by
   clamp_wall_t along their normals; both flanks are cut, giving the
   saddle a symmetric trapezoid profile. (clamp_face_x, clamp_face_z)
   is the shifted image of the -X channel wall's bottom edge; the plane
   rises from there at dovetail_angle. Below the crease where it crosses
   the vertical outer face the wall is left untouched. */
clamp_face_x   = saddle_size[0] / 2 - channel_bottom_width / 2
               - clamp_wall_t * cos(dovetail_angle);
clamp_face_z   = saddle_z + saddle_size[2] - channel_depth
               + clamp_wall_t * sin(dovetail_angle);
/* Insert axis — placed so the screw tip lands clamp_bite_frac of the
   way up the rail flank, then backed out perpendicular through the wall. */
clamp_bite_x   = saddle_size[0] / 2 - channel_bottom_width / 2
               + clamp_bite_frac * channel_depth * tan(dovetail_angle);
clamp_bite_z   = saddle_z + saddle_size[2] - channel_depth
               + clamp_bite_frac * channel_depth;
clamp_center_x = clamp_bite_x - clamp_wall_t * cos(dovetail_angle);
clamp_center_z = clamp_bite_z + clamp_wall_t * sin(dovetail_angle);

/* Heat-set brass insert — for mounting on a photography tripod QR plate.
   Insert is 8mm OD × 8mm long. Bore is a plain cylinder cut into the
   bottom face; the insert is pushed in with a soldering iron from below,
   melting the plastic around its knurled OD for a permanent fit.
   The tripod screw threads up into the insert's internal thread.
   Bore diameter is 0.2mm undersize (7.8mm) so the melted plastic can
   flow into the knurls and lock the insert in place. Bore depth is 0.5mm
   deeper than the insert so it seats flush and displaced material has
   somewhere to escape. */
insert_od         = 8.0;                     // your insert's outer diameter
insert_length     = 8.0;                     // your insert's length
insert_bore_dia   = insert_od - 0.2;         // 7.8mm — melt-in interference fit
insert_bore_depth = insert_length + 0.5;     // 8.5mm — insert length + seating relief
insert_x          = block_width / 2;         // bore centred in X
insert_y          = block_length / 2;        // bore centred in Y


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

    // Sloped outer walls — cut both saddle flanks parallel to the
    // dovetail channel walls, leaving uniform clamp_wall_t of material
    // and a symmetric trapezoid profile. Below the crease each plane
    // sits outside the part, so the cutters remove nothing there and
    // the walls stay vertical.
    translate([clamp_face_x, -1, clamp_face_z])
        rotate([0, dovetail_angle, 0])
            translate([-100, 0, -50])
                cube([100, block_length + 2, 100]);
    translate([saddle_size[0] - clamp_face_x, -1, clamp_face_z])
        rotate([0, -dovetail_angle, 0])
            translate([0, 0, -50])
                cube([100, block_length + 2, 100]);

    // M4 clamp-insert bores — perpendicular to the -X sloped face, one
    // near each Y end of the saddle. Insert bore at the face, M4
    // clearance continuing through the wall into the channel.
    for (y = [saddle_size[1] / 2 - 15, saddle_size[1] / 2 + 15])
        translate([clamp_center_x, y, clamp_center_z])
            rotate([0, 90 + dovetail_angle, 0]) {
                translate([0, 0, -0.1])
                    cylinder(d = clamp_insert_bore, h = clamp_insert_depth + 0.1);
                translate([0, 0, -0.1])
                    cylinder(d = clamp_screw_clear, h = clamp_wall_t + 3);
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

    // Heat-set brass insert bore — plain cylinder cut into the bottom face,
    // 7.8mm dia × 8.5mm deep. Insert is installed from below with a
    // soldering iron; the tripod screw threads up into it from the QR plate.
    // The tiny -0.01/+0.02 offsets on Z avoid coplanar-face rendering
    // artefacts on the bottom skin.
    translate([insert_x, insert_y, -0.01])
        cylinder(d = insert_bore_dia, h = insert_bore_depth + 0.02);
}

// ============================================================
// VISUALIZATION — temporary laser pointer cylinder (not part of the print)
// ============================================================
// The `%` modifier renders this as translucent grey for reference and
// excludes it from the actual geometry / STL export.
%translate([block_width / 2, -10, laser_center_z])
    rotate([-90, 0, 0])
        cylinder(d = laser_diameter, h = block_length + 20);
