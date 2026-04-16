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


def local_ip() -> str | None:
    """Best-effort LAN IP address of this host, or None if no LAN is available.

    Opens a UDP socket to a public address (no data sent — UDP doesn't
    establish a connection) to make the kernel pick the default-route
    interface, then reads getsockname() to find the IP it would use.

    Returns None when the probe fails (e.g. no network interface, no route,
    firewalled) or when the kernel hands back a loopback/unspecified address
    that wouldn't be reachable from another device on the LAN.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except OSError:
        return None
    # Some kernels return 0.0.0.0 or a loopback on a machine with no default
    # route; that's not a real LAN IP.
    if not ip or ip.startswith("127.") or ip == "0.0.0.0":
        return None
    return ip
