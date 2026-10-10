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

"""Tests for packaging/headless/user-data (the ready-made SD card config)."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

USER_DATA = Path(__file__).resolve().parent.parent / "packaging/headless/user-data"


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load(USER_DATA.read_text())


def test_is_cloud_config(config):
    # cloud-init ignores the file unless this is the very first line.
    assert USER_DATA.read_text().splitlines()[0] == "#cloud-config"
    assert config["hostname"] == "pushnav"
    assert config["manage_etc_hosts"] is True


def test_login_user_is_not_the_service_user(config):
    # The .deb creates its own unprivileged "pushnav" service user.
    assert [u["name"] for u in config["users"]] == ["pi"]


def test_hotspot_and_install_steps(config):
    steps = "\n".join(config["runcmd"])
    assert "do_wifi_country" in steps
    assert "802-11-wireless.mode ap" in steps and "192.168.77.1/24" in steps
    assert "nmcli con up hotspot" in steps
    assert "pushnav-headless_*_arm64.deb" in steps


def _install_step(config):
    return next(step for step in config["runcmd"] if "apt-get install" in step)


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
@pytest.mark.parametrize("folder", ["", "pushnav", "firmware/pushnav"])
@pytest.mark.parametrize("name", [
    "pushnav-headless_0.3.0~beta6-1_arm64.deb",  # local build
    "pushnav-headless_0.3.0.beta6-1_arm64.deb",  # GitHub's download name
])
def test_install_step_finds_the_deb(config, tmp_path, folder, name):
    boot = tmp_path / "bootfs"
    (boot / folder).mkdir(parents=True, exist_ok=True)
    (boot / folder / name).touch()
    cmd = (_install_step(config)
           .replace("/boot/firmware", str(boot))
           .replace("DEBIAN_FRONTEND=noninteractive apt-get install -y", "echo"))
    out = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True)
    assert out.stdout.strip() == str(boot / folder / name)


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_install_step_reports_a_missing_deb(config, tmp_path):
    boot = tmp_path / "bootfs"
    boot.mkdir()
    cmd = _install_step(config).replace("/boot/firmware", str(boot))
    out = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True)
    assert "PushNav .deb not found on the boot partition" in out.stderr
