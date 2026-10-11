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

"""Tests for evf.network.local_ip (LAN address shown in the Connectivity panel)."""

import sys

import pytest

from evf import network
from evf.config.manager import ConfigManager
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver import server as server_mod
from evf.webserver.server import WebServer


def _patch(monkeypatch, default_route, interfaces):
    monkeypatch.setattr(network, "_default_route_ip", lambda: default_route)
    monkeypatch.setattr(network, "_interface_ips", lambda: interfaces)


def test_uses_the_default_route_address(monkeypatch):
    _patch(monkeypatch, "192.168.0.115", [("wlan0", "10.0.0.5")])
    assert network.local_ip() == "192.168.0.115"


def test_hotspot_without_default_route_uses_the_wifi_address(monkeypatch):
    # A Pi running its own hotspot is the gateway: no default route.
    _patch(monkeypatch, None, [("lo", "127.0.0.1"), ("wlan0", "192.168.77.1")])
    assert network.local_ip() == "192.168.77.1"


@pytest.mark.parametrize("unusable", ["0.0.0.0", "127.0.0.1"])
def test_unusable_default_route_address_falls_back(monkeypatch, unusable):
    _patch(monkeypatch, unusable, [("eth0", "192.168.1.20")])
    assert network.local_ip() == "192.168.1.20"


def test_fallback_prefers_wifi_then_ethernet_and_skips_bridges(monkeypatch):
    _patch(monkeypatch, None, [
        ("docker0", "172.17.0.1"),
        ("br-1a2b", "172.18.0.1"),
        ("tun0", "10.8.0.2"),
        ("eth0", "192.168.1.20"),
        ("wlan0", "192.168.77.1"),
    ])
    assert network.local_ip() == "192.168.77.1"
    _patch(monkeypatch, None, [("tun0", "10.8.0.2"), ("eth0", "192.168.1.20")])
    assert network.local_ip() == "192.168.1.20"


def test_none_without_a_usable_address(monkeypatch):
    _patch(monkeypatch, None, [
        ("lo", "127.0.0.1"), ("docker0", "172.17.0.1"), ("wlan0", "169.254.3.4"),
    ])
    assert network.local_ip() is None
    _patch(monkeypatch, None, [])
    assert network.local_ip() is None


def test_interface_listing_failure_means_none(monkeypatch):
    def boom():
        raise OSError("ioctl failed")

    monkeypatch.setattr(network, "_default_route_ip", lambda: None)
    monkeypatch.setattr(network, "_interface_ips", boom)
    assert network.local_ip() is None


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux ioctl")
def test_interface_ips_reads_loopback_on_linux():
    assert ("lo", "127.0.0.1") in network._interface_ips()


def test_web_url_follows_the_current_address(tmp_path, monkeypatch):
    # The hotspot / Wi-Fi may come up after PushNav starts, so the URL in
    # the Connectivity panel must not be fixed at server start.
    cfg = ConfigManager(config_dir=tmp_path / "cfg")
    ws = WebServer(PointingState(), StateMachine(), GotoTarget(), cfg)
    port = cfg.web_port
    monkeypatch.setattr(server_mod, "local_ip", lambda: None)
    assert ws.url is None
    monkeypatch.setattr(server_mod, "local_ip", lambda: "192.168.77.1")
    assert ws.url == f"http://192.168.77.1:{port}"
