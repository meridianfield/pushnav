# /// script
# requires-python = ">=3.10"
# dependencies = ["pyvista>=0.44", "numpy", "pillow"]
# ///
"""Render the website's 3D-model images from the STLs in hardware/3d_models/stls.

    uv run scripts/render_3d_models.py            # all images
    uv run scripts/render_3d_models.py v4 laser   # only some

Writes docs/assets/3d_model_<name>.png. Parts are assembled from their
print-orientation STLs with the same offsets the .scad files use, so
re-export the STLs first after changing a design.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyvista as pv
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
STLS = REPO / "hardware" / "3d_models" / "stls"
OUT = REPO / "docs" / "assets"

SIZE = (1600, 1100)              # final image, px
BG_CENTER = (246, 247, 249)      # soft radial studio backdrop
BG_EDGE = (222, 225, 230)

# Filament-like colours
CHARCOAL = "#3a3f47"             # camera housing and hood (opaque, as printed)
SLATE = "#56606e"                # mounts
PI_BOX = "#b4bac3"               # Pi box base
PI_LID = "#c3c8cf"               # Pi box lid
ALUMINIUM = "#b8bcc2"            # stand-in laser pointer


def translate(x=0.0, y=0.0, z=0.0) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


# housing_v4.scad: YAPP box coordinates → mount frame (_box_on_mount)
BOX_ON_MOUNT = np.array([[0, 1, 0, -65 / 2],
                         [0, 0, 1, -47.9],
                         [1, 0, 0, 12],
                         [0, 0, 0, 1]], dtype=float)
# YAPP lays the lid out top-down beside the base; this puts it back on top
LID_ON_BASE = np.array([[1, 0, 0, 0],
                        [0, -1, 0, 150],
                        [0, 0, -1, 17.9],
                        [0, 0, 0, 1]], dtype=float)
V3_BASE = translate(z=12.3)      # housing bottom face on the seat
V3_HOOD = translate(z=33.3)      # hood screwed home in the lip


@dataclass
class Part:
    stl: str | None
    color: str
    xf: np.ndarray = field(default_factory=lambda: np.eye(4))
    mesh: pv.PolyData | None = None   # instead of an STL
    metallic: bool = False


@dataclass
class Shot:
    parts: list[Part]
    view: tuple[float, float, float]   # direction from the focal point to the camera
    up: tuple[float, float, float]
    zoom: float = 1.0


def laser_pointer() -> pv.PolyData:
    # laser_pointer_v3.scad's preview cylinder, lengthened to pointer size
    body = pv.Cylinder(center=(25, 23, 10 + 11.5 * np.sqrt(2)), direction=(0, 1, 0),
                       radius=11.5, height=120, resolution=120, capping=True)
    return body.triangulate()


SHOTS: dict[str, Shot] = {
    "v4": Shot([
        Part("housing_v4_mount.stl", SLATE),
        Part("housing_v4_box_base.stl", PI_BOX, BOX_ON_MOUNT),
        Part("housing_v4_box_lid.stl", PI_LID, BOX_ON_MOUNT @ LID_ON_BASE),
        Part("housing_v3_base.stl", CHARCOAL, V3_BASE),
        Part("housing_v3_hood.stl", CHARCOAL, V3_HOOD),
    ], view=(0.95, 0.55, 1.0), up=(0, 1, 0)),
    "v4_parts": Shot([   # exploded: box up off the riser, lid up off the box,
                         # camera forward off its seat along the knob's axis
        Part("housing_v4_mount.stl", SLATE),
        Part("housing_v4_box_base.stl", PI_BOX, translate(y=8) @ BOX_ON_MOUNT),
        Part("housing_v4_box_lid.stl", PI_LID, translate(y=24) @ BOX_ON_MOUNT @ LID_ON_BASE),
        Part("housing_v3_base.stl", CHARCOAL, translate(y=40, z=50) @ V3_BASE),
        Part("housing_v3_hood.stl", CHARCOAL, translate(y=40, z=50) @ V3_HOOD),
    ], view=(-1.0, 0.7, 0.85), up=(0, 1, 0), zoom=0.92),
    "v3": Shot([
        Part("housing_v3_mount.stl", SLATE),
        Part("housing_v3_base.stl", CHARCOAL, V3_BASE),
        Part("housing_v3_hood.stl", CHARCOAL, V3_HOOD),
    ], view=(0.95, 0.55, 1.0), up=(0, 1, 0)),
    "v2": Shot([
        Part("housing_v2_base.stl", CHARCOAL),
        Part("housing_v2_hood.stl", CHARCOAL, translate(z=15)),
    ], view=(0.95, 0.55, 1.0), up=(0, 1, 0)),
    "v1": Shot([
        Part("housing_base_selftap.stl", CHARCOAL),
        Part("housing_hood.stl", CHARCOAL, translate(z=15)),
    ], view=(0.95, 0.55, 1.0), up=(0, 1, 0)),
    "laser_pointer_holder": Shot([
        Part("laser_pointer_holder.stl", CHARCOAL),
        Part(None, ALUMINIUM, mesh=laser_pointer(), metallic=True),
    ], view=(0.9, -1.1, 0.75), up=(0, 0, 1)),
    "camera_base": Shot([
        Part("camera_base.stl", CHARCOAL),
    ], view=(0.8, -1.0, 1.1), up=(0, 0, 1), zoom=0.9),
    "lock_ring": Shot([
        Part("lock_ring.stl", CHARCOAL),
    ], view=(0.6, -1.0, 1.3), up=(0, 0, 1), zoom=0.9),
}


def load(part: Part) -> pv.PolyData:
    mesh = part.mesh if part.mesh is not None else pv.read(STLS / part.stl)
    return mesh.clean(tolerance=1e-6).transform(part.xf, inplace=False)


def render(shot: Shot) -> Image.Image:
    p = pv.Plotter(off_screen=True, window_size=SIZE, lighting="none")
    for part in shot.parts:
        p.add_mesh(load(part), color=part.color, smooth_shading=True,
                   split_sharp_edges=True, feature_angle=35,
                   ambient=0.18, diffuse=0.85,
                   specular=0.55 if part.metallic else 0.22,
                   specular_power=40 if part.metallic else 18)

    p.camera_position = "xy"
    p.reset_camera()
    focal = np.array(p.camera.focal_point)
    view = np.array(shot.view, dtype=float)
    view /= np.linalg.norm(view)
    p.camera.position = focal + view * 1000
    p.camera.up = shot.up
    p.camera.view_angle = 22
    p.reset_camera()
    p.camera.zoom(1.25 * shot.zoom)

    # Studio lights, attached to the camera so every shot is lit alike:
    # warm key from upper left, cool fill from the right, rim from behind
    for pos, color, intensity in [((-1.0, 1.2, 1.0), "#fff6ec", 0.75),
                                  ((1.3, 0.2, 0.8), "#e8f0ff", 0.55),
                                  ((0.2, 1.0, -1.5), "#ffffff", 0.6),
                                  ((0.0, -1.0, 0.6), "#ffffff", 0.25)]:
        light = pv.Light(position=pos, focal_point=(0, 0, 0), color=color,
                         intensity=intensity, light_type="camera light")
        p.add_light(light)

    p.enable_ssao(radius=4, bias=0.05, kernel_size=128, blur=True)
    p.enable_anti_aliasing("ssaa")
    rgba = p.screenshot(transparent_background=True, return_img=True)
    p.close()
    return compose(Image.fromarray(rgba, "RGBA"))


def compose(subject: Image.Image) -> Image.Image:
    w, h = subject.size
    # radial backdrop
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / (w * 0.62), (yy - h * 0.42) / (h * 0.75)).clip(0, 1)
    bg = (np.array(BG_CENTER) * (1 - r[..., None]) + np.array(BG_EDGE) * r[..., None])
    canvas = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")

    # soft contact shadow under the subject
    alpha = np.array(subject.split()[-1])
    ys, xs = np.nonzero(alpha > 8)
    if len(xs):
        x0, x1, y1 = xs.min(), xs.max(), ys.max()
        sw = (x1 - x0) * 0.86
        sh = sw * 0.075
        shadow = Image.new("L", (w, h), 0)
        ImageDraw.Draw(shadow).ellipse(
            [(x0 + x1) / 2 - sw / 2, y1 - sh * 0.75, (x0 + x1) / 2 + sw / 2, y1 + sh * 0.6],
            fill=110)
        shadow = shadow.filter(ImageFilter.GaussianBlur(28))
        dark = Image.new("RGBA", (w, h), (40, 44, 52, 0))
        dark.putalpha(shadow)
        canvas = Image.alpha_composite(canvas, dark)

    return Image.alpha_composite(canvas, subject).convert("RGB")


def main(names: list[str]) -> None:
    for name in names or SHOTS:
        out = OUT / f"3d_model_{name}.png"
        render(SHOTS[name]).save(out, optimize=True)
        print(f"wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main(sys.argv[1:])
