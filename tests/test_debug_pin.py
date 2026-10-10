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

"""Tests for the GPIO21 debug-mode jumper (evf.engine.debug_pin)."""

import struct
from pathlib import Path

import pytest

from evf.engine import debug_pin as dp

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_ioctl_numbers_match_the_kernel_headers():
    # Values of the macros in include/uapi/linux/gpio.h on 64-bit Linux.
    assert dp.GPIO_GET_CHIPINFO_IOCTL == 0x8044B401
    assert dp.GPIO_V2_GET_LINE_IOCTL == 0xC250B407
    assert dp.GPIO_V2_LINE_GET_VALUES_IOCTL == 0xC010B40E


def test_line_request_layout():
    req = dp._line_request(21)
    assert len(req) == 592
    assert struct.unpack_from("I", req, 0) == (21,)
    assert req[256:256 + 13] == b"pushnav-debug"
    flags = struct.unpack_from("Q", req, 288)[0]
    assert flags == (1 << 2) | (1 << 8)  # INPUT | BIAS_PULL_UP
    assert struct.unpack_from("I", req, 296) == (0,)  # num_attrs
    assert struct.unpack_from("I", req, 560) == (1,)  # num_lines


@pytest.mark.parametrize("label", ["pinctrl-rp1", "pinctrl-bcm2711", "pinctrl-bcm2835"])
def test_header_chip_found_by_label(tmp_path, monkeypatch, label):
    for name in ("gpiochip0", "gpiochip1", "gpiochip2"):
        (tmp_path / name).touch()
    labels = {"gpiochip0": "pinctrl-bcm2712", "gpiochip1": label,
              "gpiochip2": "raspberrypi-exp-gpio"}
    monkeypatch.setattr(dp, "_chip_label", lambda chip: labels[chip.name])
    assert dp.header_chip(tmp_path) == (tmp_path / "gpiochip1", label)


def test_header_chip_none_on_other_hardware(tmp_path, monkeypatch):
    (tmp_path / "gpiochip0").touch()
    monkeypatch.setattr(dp, "_chip_label", lambda chip: "gpio-amd-fch")
    assert dp.header_chip(tmp_path) is None
    assert dp.header_chip(tmp_path / "missing") is None


def _run(tmp_path, monkeypatch, fitted):
    flag = tmp_path / "run" / "debug"
    if isinstance(fitted, Exception):
        def boom(dev):
            raise fitted
        monkeypatch.setattr(dp, "debug_jumper_fitted", boom)
    else:
        monkeypatch.setattr(dp, "debug_jumper_fitted", lambda dev: fitted)
    assert dp.main(["--flag", str(flag)]) == 0
    return flag


def test_main_creates_the_flag_when_jumpered(tmp_path, monkeypatch):
    flag = _run(tmp_path, monkeypatch, True)
    assert flag.exists() and dp.debug_flag_set(flag)


def test_main_removes_a_stale_flag_without_jumper(tmp_path, monkeypatch):
    flag = tmp_path / "run" / "debug"
    flag.parent.mkdir()
    flag.write_text("stale\n")
    _run(tmp_path, monkeypatch, False)
    assert not flag.exists() and not dp.debug_flag_set(flag)


def test_main_never_fails_and_leaves_debug_off(tmp_path, monkeypatch):
    flag = tmp_path / "run" / "debug"
    flag.parent.mkdir()
    flag.write_text("stale\n")
    _run(tmp_path, monkeypatch, OSError("Device or resource busy"))
    assert not flag.exists()


def test_check_prints_the_pin_state(tmp_path, monkeypatch, capsys):
    flag = tmp_path / "debug"
    monkeypatch.setattr(dp, "header_chip",
                        lambda dev: (Path("/dev/gpiochip0"), "pinctrl-bcm2835"))
    monkeypatch.setattr(dp, "read_jumper", lambda chip: True)
    assert dp.main(["--check", "--flag", str(flag)]) == 0
    assert "GPIO21 reads low" in capsys.readouterr().out
    assert not flag.exists()  # --check never touches the flag


def test_service_unit_runs_the_check_before_pushnav():
    unit = (REPO_ROOT / "packaging/headless/pushnav-headless.service").read_text()
    assert "RuntimeDirectory=pushnav-headless" in unit
    assert "ExecStartPre=+" in unit and "-m evf.engine.debug_pin" in unit
    assert dp.DEBUG_FLAG == Path("/run/pushnav-headless/debug")
