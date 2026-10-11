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

"""Network utilities shared across subsystems."""

import socket
import struct
import sys

_SIOCGIFADDR = 0x8915  # Linux: read an interface's IPv4 address
# Interface name prefixes in order of preference for the fallback; anything
# else that isn't skipped comes last. Containers and VMs bridges are skipped.
_PREFERRED_PREFIXES = ("wlan", "wl", "eth", "en")
_SKIPPED_PREFIXES = ("lo", "docker", "br-", "veth", "virbr", "vnet", "tailscale")


def _usable(ip: str | None) -> bool:
    # 0.0.0.0 / loopback aren't reachable from another device, and 169.254.x.x
    # is a link-local address the OS assigns when there's no DHCP.
    return bool(ip) and ip != "0.0.0.0" and not ip.startswith(("127.", "169.254."))


def _default_route_ip() -> str | None:
    """IP of the default-route interface, or None without a default route.

    Opens a UDP socket to a public address (no data sent — UDP doesn't
    establish a connection) to make the kernel pick the default-route
    interface, then reads getsockname() to find the IP it would use.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _interface_ips() -> list[tuple[str, str]]:
    """(name, IPv4) for every interface that has one. Linux only, else []."""
    if not sys.platform.startswith("linux"):
        return []
    import fcntl

    found = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for _, name in socket.if_nameindex():
            try:
                ifreq = struct.pack("256s", name.encode()[:15])
                res = fcntl.ioctl(s.fileno(), _SIOCGIFADDR, ifreq)
            except OSError:  # no IPv4 address on this interface
                continue
            found.append((name, socket.inet_ntoa(res[20:24])))
    return found


def _rank(name: str) -> int:
    for i, prefix in enumerate(_PREFERRED_PREFIXES):
        if name.startswith(prefix):
            return i
    return len(_PREFERRED_PREFIXES)


def local_ip() -> str | None:
    """Best-effort LAN IP address of this host, or None if no LAN is available.

    Uses the default-route interface's address when there is a default
    route. A Raspberry Pi running its own Wi-Fi hotspot has none (it *is*
    the network's gateway), so then fall back to the address of a Wi-Fi or
    Ethernet interface, read directly from the interface (Linux only).

    Returns None when neither finds a usable address: no network, or only
    loopback / link-local / unspecified addresses that another device on
    the LAN couldn't reach.
    """
    ip = _default_route_ip()
    if _usable(ip):
        return ip
    try:
        candidates = [
            (name, addr) for name, addr in _interface_ips()
            if _usable(addr) and not name.startswith(_SKIPPED_PREFIXES)
        ]
    except OSError:
        return None
    if not candidates:
        return None
    return min(candidates, key=lambda c: _rank(c[0]))[1]
