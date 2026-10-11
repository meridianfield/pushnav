#!/usr/bin/env python3
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

"""Make a 50 x 20 mm label for a ready-made PushNav Raspberry Pi.

The label has a QR code for the web app on the left, and on the right the
hotspot name and password, the web address and the SSH login. The
passwords and the hotspot address come from the SD card's user-data file,
so a card whose passwords were changed gets a matching label.

    uv run python scripts/make_pi_label.py 3F2A
    uv run python scripts/make_pi_label.py PushNav-3F2A --user-data ~/my-user-data

The argument is the hotspot name's 4-character suffix (from the Pi's
serial number), as the phone's Wi-Fi list shows it. The label is written
as pushnav-label-<suffix>.svg, plus a .png next to it (300 dpi unless
--dpi says otherwise); -o picks another SVG name. All text is converted to
outlines (Atkinson Hyperlegible, from scripts/fonts/), so the label looks
the same in any app, with no font to install.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import segno
import uharfbuzz as hb
import yaml
from fontTools.pens.freetypePen import FreeTypePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = Path(__file__).resolve().parent / "fonts"
DEFAULT_USER_DATA = REPO_ROOT / "packaging/headless/user-data"
DEFAULT_PORT = 8765
DEFAULT_DPI = 300

# Label geometry, in mm
WIDTH, HEIGHT = 50.0, 20.0
QR_SIZE = 16.0
QR_X = QR_Y = 2.0                  # the QR code's white surround (~3 modules)
TEXT_GAP = 2.2                     # QR code to text
RIGHT_MARGIN = 1.5
TITLE_SIZE = 4.6                   # font size (em) of "PushNav"
BODY_MAX, BODY_MIN = 3.0, 2.0      # font size range of the four lines
WORD_GAP = 1.1                     # "Wi-Fi" to its value
LINE_PITCH = 1.12                  # line spacing, in ems


@dataclass(frozen=True)
class LabelInfo:
    ssid: str
    wifi_password: str
    ip: str
    port: int
    ssh_user: str
    ssh_password: str

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    @property
    def rows(self) -> list[tuple[str, str]]:
        return [
            ("Wi-Fi", self.ssid),
            ("Pass", self.wifi_password),
            ("Web", f"{self.ip}:{self.port}"),
            ("SSH", f"{self.ssh_user} / {self.ssh_password}"),
        ]


@dataclass(frozen=True)
class Layout:
    body_size: float               # font size of the four lines, mm
    text_right: float              # right edge of the widest line
    text_bottom: float             # lowest descender


def parse_suffix(value: str) -> str:
    """'3f2a' or 'PushNav-3F2A' -> '3F2A'."""
    m = re.fullmatch(r"(?:PushNav-)?([0-9A-Fa-f]{4})", value.strip())
    if not m:
        raise ValueError(
            f"{value!r}: expected the 4 characters after 'PushNav-' in the "
            "hotspot name, e.g. 3F2A"
        )
    return m.group(1).upper()


def settings_from_user_data(path: Path) -> dict:
    """Hotspot password and address, and the SSH login, from a user-data file."""
    cfg = yaml.safe_load(path.read_text())
    users = [u for u in cfg.get("users") or [] if isinstance(u, dict)]
    user = next((u for u in users if "plain_text_passwd" in u), None)
    commands = " ".join(c if isinstance(c, str) else " ".join(c)
                        for c in cfg.get("runcmd") or [])
    psk = re.search(r'wifi-sec\.psk\s+"([^"]*)"', commands)
    ip = re.search(r"ipv4\.addresses\s+([0-9.]+)/", commands)
    missing = [name for name, found in [
        ("a user with plain_text_passwd", user),
        ('wifi-sec.psk "..." in runcmd', psk),
        ("ipv4.addresses in runcmd", ip),
    ] if not found]
    if missing:
        raise ValueError(f"{path}: can't find {', '.join(missing)}")
    return {
        "wifi_password": psk.group(1),
        "ip": ip.group(1),
        "ssh_user": user["name"],
        "ssh_password": str(user["plain_text_passwd"]),
    }


class _Font:
    def __init__(self, path: Path):
        tt = TTFont(path)
        self.upem = tt["head"].unitsPerEm
        self.cap_height = tt["OS/2"].sCapHeight / self.upem
        self.descender = -tt["hhea"].descent / self.upem
        self.glyph_set = tt.getGlyphSet()
        self.glyph_order = tt.getGlyphOrder()
        self.hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))

    def _shape(self, text: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"kern": True, "liga": False})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text: str, size: float) -> float:
        _, positions = self._shape(text)
        return sum(p.x_advance for p in positions) * size / self.upem

    def draw(self, pen, text: str, x: float, baseline: float, size: float) -> None:
        """Draw text starting at x on the given baseline (mm, y down)."""
        infos, positions = self._shape(text)
        scale = size / self.upem
        advance = 0
        for info, pos in zip(infos, positions):
            # Decompose composite glyphs here, with this font's glyphs, so
            # the pen never needs a glyph set of its own
            rec = DecomposingRecordingPen(self.glyph_set)
            self.glyph_set[self.glyph_order[info.codepoint]].draw(rec)
            # font units (y up) -> mm (y down)
            dx = x + (advance + pos.x_offset) * scale
            dy = baseline - pos.y_offset * scale
            rec.replay(TransformPen(pen, (scale, 0, 0, -scale, dx, dy)))
            advance += pos.x_advance


@lru_cache(maxsize=None)
def _fonts() -> tuple[_Font, _Font]:
    return (_Font(FONT_DIR / "AtkinsonHyperlegible-Regular.ttf"),
            _Font(FONT_DIR / "AtkinsonHyperlegible-Bold.ttf"))


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def _draw_qr(pen, url: str) -> None:
    """The QR code: a rectangle per horizontal run of dark modules."""
    matrix = segno.make(url, error="m", boost_error=False).matrix
    m = QR_SIZE / len(matrix)
    for r, row in enumerate(matrix):
        c = 0
        while c < len(row):
            if not row[c]:
                c += 1
                continue
            start = c
            while c < len(row) and row[c]:
                c += 1
            x0, x1 = QR_X + start * m, QR_X + c * m
            y0, y1 = QR_Y + r * m, QR_Y + (r + 1) * m
            pen.moveTo((x0, y0))
            pen.lineTo((x1, y0))
            pen.lineTo((x1, y1))
            pen.lineTo((x0, y1))
            pen.closePath()


def _draw(info: LabelInfo, qr_pen, text_pen) -> Layout:
    """Draw the label in mm (y down): the QR code into qr_pen, text into text_pen."""
    regular, bold = _fonts()
    rows = info.rows
    tx = QR_X + QR_SIZE + TEXT_GAP
    right = WIDTH - RIGHT_MARGIN

    # Largest font size at which the widest line fits
    size = BODY_MAX
    while True:
        words_w = max(bold.width(k, size) for k, _ in rows) + WORD_GAP
        values_w = max(regular.width(v, size) for _, v in rows)
        if tx + words_w + values_w <= right:
            break
        size = round(size - 0.05, 2)
        if size < BODY_MIN:
            widest = max(rows, key=lambda r: regular.width(r[1], BODY_MIN))[1]
            raise ValueError(f"{widest!r} is too long to fit on the label")

    # Title on top, aligned with the QR code's top; the last line's
    # baseline on the QR code's bottom edge
    title_base = QR_Y + bold.cap_height * TITLE_SIZE
    last_base = QR_Y + QR_SIZE
    pitch = size * LINE_PITCH
    _draw_qr(qr_pen, info.url)
    bold.draw(text_pen, "PushNav", tx - 0.15, title_base, TITLE_SIZE)
    for i, (word, value) in enumerate(rows):
        base = last_base - pitch * (len(rows) - 1 - i)
        bold.draw(text_pen, word, tx, base, size)
        regular.draw(text_pen, value, tx + words_w, base, size)

    return Layout(
        body_size=size,
        text_right=tx + words_w + values_w,
        text_bottom=last_base + regular.descender * size,
    )


def make_label(info: LabelInfo) -> tuple[str, Layout]:
    """The label as an SVG document, 50 x 20 mm."""
    qr, text = SVGPathPen(None, ntos=_num), SVGPathPen(None, ntos=_num)
    layout = _draw(info, qr, text)
    desc = "; ".join(f"{k} {v}" for k, v in info.rows)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_num(WIDTH)}mm" height="{_num(HEIGHT)}mm" '
        f'viewBox="0 0 {_num(WIDTH)} {_num(HEIGHT)}">\n'
        f"  <title>PushNav label: {info.ssid}</title>\n"
        f"  <desc>QR code: {info.url}; {_xml_escape(desc)}</desc>\n"
        f'  <rect width="{_num(WIDTH)}" height="{_num(HEIGHT)}" fill="#fff"/>\n'
        f'  <path id="qr" fill="#000" d="{qr.getCommands()}"/>\n'
        f'  <path id="text" fill="#000" d="{text.getCommands()}"/>\n'
        "</svg>\n"
    )
    return svg, layout


def make_png(info: LabelInfo, dpi: int = DEFAULT_DPI) -> Image.Image:
    """The label as an anti-aliased greyscale image at the given dpi."""
    px_per_mm = dpi / 25.4
    w, h = round(WIDTH * px_per_mm), round(HEIGHT * px_per_mm)
    pen = FreeTypePen(None)
    # mm, y down -> pixels, y up from the bottom-left (FreeType's bitmap)
    to_px = TransformPen(pen, (px_per_mm, 0, 0, -px_per_mm, 0, h))
    _draw(info, to_px, to_px)
    coverage = pen.image(width=w, height=h).getchannel("A")
    img = Image.new("L", (w, h), 255)
    img.paste(0, mask=coverage)
    img.info["dpi"] = (dpi, dpi)
    return img


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Make a 50 x 20 mm SVG label for a ready-made PushNav Pi.")
    p.add_argument("suffix", help="the 4 characters after 'PushNav-' in the hotspot "
                                  "name (e.g. 3F2A), or the whole name")
    p.add_argument("--user-data", type=Path, default=DEFAULT_USER_DATA,
                   help="the SD card's user-data file, for the passwords and "
                        "address (default: %(default)s)")
    p.add_argument("--wifi-password", help="hotspot password (overrides user-data)")
    p.add_argument("--ssh-user", help="SSH login name (overrides user-data)")
    p.add_argument("--ssh-password", help="SSH password (overrides user-data)")
    p.add_argument("--ip", help="hotspot address (overrides user-data)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help="web app port (default: %(default)s)")
    p.add_argument("-o", "--output", type=Path,
                   help="SVG file to write; the PNG goes next to it "
                        "(default: pushnav-label-<suffix>.svg)")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI,
                   help="PNG resolution (default: %(default)s)")
    args = p.parse_args(argv)

    try:
        suffix = parse_suffix(args.suffix)
        settings = settings_from_user_data(args.user_data)
        for key in ("wifi_password", "ip", "ssh_user", "ssh_password"):
            if getattr(args, key) is not None:
                settings[key] = getattr(args, key)
        if not 72 <= args.dpi <= 2400:
            raise ValueError(f"--dpi {args.dpi}: use 72 to 2400")
        info = LabelInfo(ssid=f"PushNav-{suffix}", port=args.port, **settings)
        svg, _ = make_label(info)
        png = make_png(info, args.dpi)
        out = args.output or Path(f"pushnav-label-{suffix}.svg")
        png_out = out.with_suffix(".png")
        out.write_text(svg)
        png.save(png_out, dpi=(args.dpi, args.dpi))
    except (OSError, ValueError) as exc:
        print(f"make_pi_label: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {out}")
    print(f"Wrote {png_out} ({png.width} x {png.height} px, {args.dpi} dpi)")
    for word, value in info.rows:
        print(f"  {word:6} {value}")
    print(f"  QR     {info.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
