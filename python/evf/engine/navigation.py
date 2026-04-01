# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PushNav is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PushNav. If not, see <https://www.gnu.org/licenses/>.

"""Pure-function navigation math for GOTO guidance.

All angles in degrees unless noted. Uses math (not numpy) for scalar ops.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationResult:
    """Complete navigation computation result."""

    separation_deg: float
    sky_position_angle_deg: float  # bearing from current to target, east of north
    camera_angle_deg: float  # 0=top, 90=right, 180=bottom, 270=left
    delta_right_deg: float  # positive = move scope right (target is right in camera)
    delta_up_deg: float  # positive = move scope up (target is up in camera)
    direction_text: str  # e.g. "3.2° R  1.5° U"
    pixel_x: float | None  # projected pixel x (None if behind camera)
    pixel_y: float | None  # projected pixel y (None if behind camera)
    in_fov: bool  # True if target falls within the image bounds


def angular_separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Angular separation between two sky positions using the Vincenty formula.

    All inputs and output in degrees.
    """
    ra1_r = math.radians(ra1)
    dec1_r = math.radians(dec1)
    ra2_r = math.radians(ra2)
    dec2_r = math.radians(dec2)
    dra = ra2_r - ra1_r

    cos_dec1 = math.cos(dec1_r)
    cos_dec2 = math.cos(dec2_r)
    sin_dec1 = math.sin(dec1_r)
    sin_dec2 = math.sin(dec2_r)

    num1 = cos_dec2 * math.sin(dra)
    num2 = cos_dec1 * sin_dec2 - sin_dec1 * cos_dec2 * math.cos(dra)
    numerator = math.sqrt(num1 * num1 + num2 * num2)
    denominator = sin_dec1 * sin_dec2 + cos_dec1 * cos_dec2 * math.cos(dra)

    return math.degrees(math.atan2(numerator, denominator))


def sky_position_angle(
    ra1: float, dec1: float, ra2: float, dec2: float
) -> float:
    """Position angle from point 1 to point 2, east of north, [0, 360).

    All inputs and output in degrees.
    """
    ra1_r = math.radians(ra1)
    dec1_r = math.radians(dec1)
    ra2_r = math.radians(ra2)
    dec2_r = math.radians(dec2)
    dra = ra2_r - ra1_r

    y = math.sin(dra) * math.cos(dec2_r)
    x = math.cos(dec1_r) * math.sin(dec2_r) - math.sin(dec1_r) * math.cos(
        dec2_r
    ) * math.cos(dra)

    pa = math.degrees(math.atan2(y, x))
    return pa % 360.0


def gnomonic_project(
    ra0: float,
    dec0: float,
    roll: float,
    ra_t: float,
    dec_t: float,
    fov_h: float,
    img_w: int,
    img_h: int,
) -> tuple[float, float] | None:
    """Tangent-plane projection of target onto camera image.

    Returns (pixel_x, pixel_y) with origin top-left, x right, y down.
    Returns None if target is behind camera (>90 deg from boresight).

    Coordinate convention (from tetra3's _compute_vectors):
    - At Roll=0: image-up = celestial north, image-left = celestial east
    - Roll = angle from north to image-up, east of north
    """
    ra0_r = math.radians(ra0)
    dec0_r = math.radians(dec0)
    rat_r = math.radians(ra_t)
    dect_r = math.radians(dec_t)
    roll_r = math.radians(roll)

    cos_dec0 = math.cos(dec0_r)
    sin_dec0 = math.sin(dec0_r)
    cos_dect = math.cos(dect_r)
    sin_dect = math.sin(dect_r)
    dra = rat_r - ra0_r

    # Standard gnomonic projection: tangent plane coordinates
    cos_c = sin_dec0 * sin_dect + cos_dec0 * cos_dect * math.cos(dra)
    if cos_c <= 0:
        return None  # behind camera

    # xi = east, eta = north in sky tangent plane
    xi = (cos_dect * math.sin(dra)) / cos_c
    eta = (cos_dec0 * sin_dect - sin_dec0 * cos_dect * math.cos(dra)) / cos_c

    # Rotate sky tangent plane into camera frame
    cos_roll = math.cos(roll_r)
    sin_roll = math.sin(roll_r)
    r_cam = -xi * cos_roll + eta * sin_roll  # rightward in image
    u_cam = xi * sin_roll + eta * cos_roll  # upward in image

    # Scale to pixels
    scale = img_w / (2.0 * math.tan(math.radians(fov_h / 2.0)))
    pixel_x = img_w / 2.0 + r_cam * scale
    pixel_y = img_h / 2.0 - u_cam * scale  # y-down

    return (pixel_x, pixel_y)


def compute_navigation(
    ra: float,
    dec: float,
    roll: float,
    target_ra: float,
    target_dec: float,
    fov_h: float,
    img_w: int,
    img_h: int,
) -> NavigationResult:
    """Compute full navigation result from current pointing to target."""
    sep = angular_separation(ra, dec, target_ra, target_dec)
    sky_pa = sky_position_angle(ra, dec, target_ra, target_dec)
    camera_angle = (sky_pa - roll) % 360.0

    cam_r = math.radians(camera_angle)
    delta_right = sep * math.sin(cam_r)
    delta_up = sep * math.cos(cam_r)

    # Format direction text
    direction_text = _format_direction(delta_right, delta_up)

    # Project target onto image
    proj = gnomonic_project(ra, dec, roll, target_ra, target_dec, fov_h, img_w, img_h)
    if proj is not None:
        px, py = proj
        in_fov = 0 <= px < img_w and 0 <= py < img_h
    else:
        px, py = None, None
        in_fov = False

    return NavigationResult(
        separation_deg=sep,
        sky_position_angle_deg=sky_pa,
        camera_angle_deg=camera_angle,
        delta_right_deg=delta_right,
        delta_up_deg=delta_up,
        direction_text=direction_text,
        pixel_x=px,
        pixel_y=py,
        in_fov=in_fov,
    )


def _format_direction(delta_right: float, delta_up: float) -> str:
    """Format camera-relative direction as e.g. '3.2° R  1.5° U'."""
    lr = "R" if delta_right >= 0 else "L"
    ud = "U" if delta_up >= 0 else "D"
    return f"{abs(delta_right):.1f}\u00b0 {lr}  {abs(delta_up):.1f}\u00b0 {ud}"


def edge_arrow_position(
    px: float,
    py: float,
    img_w: int,
    img_h: int,
    margin: int = 20,
    *,
    origin_x: float | None = None,
    origin_y: float | None = None,
) -> tuple[float, float, float]:
    """Find where the origin-to-target line intersects the image boundary.

    Returns (x, y, angle_deg) where angle is the direction the arrow points
    (toward the target), measured clockwise from image-up.

    origin_x/origin_y default to image center when not supplied.
    """
    cx = origin_x if origin_x is not None else img_w / 2.0
    cy = origin_y if origin_y is not None else img_h / 2.0
    dx = px - cx
    dy = py - cy

    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return (cx, float(margin), 0.0)

    # Arrow direction angle (clockwise from up, matching screen coords)
    angle = math.degrees(math.atan2(dx, -dy)) % 360.0

    # Inset boundaries
    left = float(margin)
    right = float(img_w - margin)
    top = float(margin)
    bottom = float(img_h - margin)

    # Find intersection with inset rectangle
    t_min = float("inf")

    # Right edge
    if dx > 0:
        t = (right - cx) / dx
        y_at = cy + t * dy
        if top <= y_at <= bottom and t < t_min:
            t_min = t

    # Left edge
    if dx < 0:
        t = (left - cx) / dx
        y_at = cy + t * dy
        if top <= y_at <= bottom and t < t_min:
            t_min = t

    # Bottom edge (y-down)
    if dy > 0:
        t = (bottom - cy) / dy
        x_at = cx + t * dx
        if left <= x_at <= right and t < t_min:
            t_min = t

    # Top edge
    if dy < 0:
        t = (top - cy) / dy
        x_at = cx + t * dx
        if left <= x_at <= right and t < t_min:
            t_min = t

    if t_min == float("inf"):
        # Fallback (shouldn't happen with valid inputs)
        t_min = 1.0

    edge_x = cx + t_min * dx
    edge_y = cy + t_min * dy

    return (edge_x, edge_y, angle)
