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

"""Tests for scripts/make_pi_label.py (the 50 x 20 mm Pi label)."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import segno
from PIL import Image

# scripts/ isn't on sys.path by default — make the module importable.
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import make_pi_label as label  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"


def _info(**overrides):
    values = dict(ssid="PushNav-3F2A", wifi_password="pushnav123", ip="192.168.77.1",
                  port=8765, ssh_user="pi", ssh_password="pushnav")
    values.update(overrides)
    return label.LabelInfo(**values)


@pytest.mark.parametrize("given", ["3F2A", "3f2a", "PushNav-3F2A", " 3f2A "])
def test_parse_suffix(given):
    assert label.parse_suffix(given) == "3F2A"


@pytest.mark.parametrize("given", ["3F2", "3F2AB", "XYZ1", "PushNav-", "pushnav-3F2A"])
def test_parse_suffix_rejects(given):
    with pytest.raises(ValueError, match="4 characters"):
        label.parse_suffix(given)


def test_settings_from_repo_user_data():
    assert label.settings_from_user_data(label.DEFAULT_USER_DATA) == {
        "wifi_password": "pushnav123",
        "ip": "192.168.77.1",
        "ssh_user": "pi",
        "ssh_password": "pushnav",
    }


def test_settings_follow_edited_user_data(tmp_path):
    # Someone changed the passwords where user-data says CHANGE
    text = label.DEFAULT_USER_DATA.read_text()
    text = text.replace('wifi-sec.psk "pushnav123"', 'wifi-sec.psk "dark-skies-42"')
    text = text.replace("plain_text_passwd: pushnav ", "plain_text_passwd: s3cret ")
    edited = tmp_path / "user-data"
    edited.write_text(text)
    settings = label.settings_from_user_data(edited)
    assert settings["wifi_password"] == "dark-skies-42"
    assert settings["ssh_password"] == "s3cret"


def test_settings_missing_hotspot(tmp_path):
    bad = tmp_path / "user-data"
    bad.write_text("#cloud-config\nusers:\n  - name: pi\n    plain_text_passwd: x\n")
    with pytest.raises(ValueError, match="wifi-sec.psk"):
        label.settings_from_user_data(bad)


def test_svg_is_50_by_20_mm_with_outlined_text():
    svg, _ = label.make_label(_info())
    root = ET.fromstring(svg)
    assert root.get("width") == "50mm"
    assert root.get("height") == "20mm"
    assert root.get("viewBox") == "0 0 50 20"
    assert root.find(f"{SVG_NS}title").text == "PushNav label: PushNav-3F2A"
    # Text is drawn as shapes: no font needed wherever the label is printed
    assert root.find(f".//{SVG_NS}text") is None
    assert "PushNav-3F2A" in root.find(f"{SVG_NS}desc").text


def _expected_qr():
    matrix = segno.make("http://192.168.77.1:8765", error="m", boost_error=False).matrix
    return [[bool(v) for v in row] for row in matrix]


def _qr_modules(path_data, n):
    """Rebuild the dark-module grid from the QR code's run rectangles."""
    runs = re.findall(r"M([\d.]+) ([\d.]+)H([\d.]+)V[\d.]+H[\d.]+Z", path_data)
    assert runs
    m = label.QR_SIZE / n
    grid = [[False] * n for _ in range(n)]
    for x0, y, x1 in runs:
        r = round((float(y) - label.QR_Y) / m)
        for c in range(round((float(x0) - label.QR_X) / m), round((float(x1) - label.QR_X) / m)):
            grid[r][c] = True
    return grid


def test_qr_code_is_the_web_address():
    svg, _ = label.make_label(_info())
    qr = next(p for p in ET.fromstring(svg).iter(f"{SVG_NS}path") if p.get("id") == "qr")
    expected = _expected_qr()
    assert _qr_modules(qr.get("d"), len(expected)) == expected


@pytest.mark.parametrize("dpi, size", [(300, (591, 236)), (600, (1181, 472))])
def test_png_size_and_dpi(dpi, size):
    img = label.make_png(_info(), dpi)
    assert img.mode == "L"
    assert img.size == size


def test_png_qr_code_is_the_web_address():
    img = label.make_png(_info(), 300)
    px_per_mm = 300 / 25.4
    expected = _expected_qr()
    m = label.QR_SIZE / len(expected)
    # sample the middle of every module: black for dark, white for light
    for r, row in enumerate(expected):
        for c, dark in enumerate(row):
            x = (label.QR_X + (c + 0.5) * m) * px_per_mm
            y = (label.QR_Y + (r + 0.5) * m) * px_per_mm
            assert (img.getpixel((int(x), int(y))) < 64) == dark, (r, c)


def test_png_has_text_and_a_white_margin():
    img = label.make_png(_info(), 300)
    px_per_mm = 300 / 25.4
    # text column: plenty of ink
    text = img.crop((round(21 * px_per_mm), 0, img.width, img.height))
    assert sum(text.histogram()[:128]) > 2000
    # the outer 1 mm stays white all round
    edge = round(1 * px_per_mm)
    for box in [(0, 0, img.width, edge), (0, img.height - edge, img.width, img.height),
                (0, 0, edge, img.height), (img.width - edge, 0, img.width, img.height)]:
        assert img.crop(box).getextrema()[0] > 250, box


def test_text_fits_on_the_label():
    _, layout = label.make_label(_info())
    assert layout.text_right <= label.WIDTH - label.RIGHT_MARGIN
    assert layout.text_bottom <= label.HEIGHT - 1.0
    assert layout.body_size >= 2.5


def test_long_password_shrinks_the_text():
    _, normal = label.make_label(_info())
    _, long = label.make_label(_info(wifi_password="observing-at-dark-site"))
    assert long.body_size < normal.body_size
    assert long.text_right <= label.WIDTH - label.RIGHT_MARGIN


def test_too_long_to_fit():
    with pytest.raises(ValueError, match="too long"):
        label.make_label(_info(wifi_password="x" * 60))


def test_cli_writes_the_label(tmp_path, capsys):
    out = tmp_path / "label.svg"
    assert label.main(["3f2a", "-o", str(out), "--ssh-password", "s3cret"]) == 0
    assert "PushNav label: PushNav-3F2A" in out.read_text()
    assert "SSH pi / s3cret" in out.read_text()
    with Image.open(tmp_path / "label.png") as png:
        assert png.size == (591, 236)
        assert round(png.info["dpi"][0]) == 300
    assert "Wrote" in capsys.readouterr().out


def test_cli_dpi(tmp_path):
    assert label.main(["3F2A", "-o", str(tmp_path / "l.svg"), "--dpi", "600"]) == 0
    with Image.open(tmp_path / "l.png") as png:
        assert png.size == (1181, 472)
        assert round(png.info["dpi"][0]) == 600


def test_cli_rejects_a_silly_dpi(tmp_path, capsys):
    assert label.main(["3F2A", "-o", str(tmp_path / "l.svg"), "--dpi", "5"]) == 1
    assert "--dpi" in capsys.readouterr().err
    assert not (tmp_path / "l.svg").exists()


def test_cli_reports_a_bad_suffix(tmp_path, capsys):
    assert label.main(["nope", "-o", str(tmp_path / "x.svg")]) == 1
    assert "4 characters" in capsys.readouterr().err
    assert not (tmp_path / "x.svg").exists()
    assert not (tmp_path / "x.png").exists()
