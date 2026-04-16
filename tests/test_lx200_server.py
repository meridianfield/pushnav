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

"""Integration tests for the LX200 TCP server."""

import socket
import time

import pytest

from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.lx200.server import Lx200Server


@pytest.fixture
def server():
    """Start an LX200 server on an ephemeral port."""
    ps = PointingState()
    gt = GotoTarget()
    srv = Lx200Server(ps, host="127.0.0.1", port=0, goto_target=gt, app_version="test")
    srv.start()
    yield srv, ps, gt
    srv.stop(timeout=2.0)


def _connect(srv: Lx200Server) -> socket.socket:
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=2.0)
    s.settimeout(2.0)
    return s


def _recv_until_hash(sock: socket.socket, max_bytes: int = 256) -> bytes:
    """Read until we see a '#' or get a single-char reply ('0' or '1')."""
    buf = b""
    start = time.time()
    while time.time() - start < 2.0 and len(buf) < max_bytes:
        try:
            chunk = sock.recv(max_bytes - len(buf))
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        if b"#" in buf or buf in (b"0", b"1"):
            break
    return buf


class TestStartStop:
    def test_server_binds_and_shuts_down(self, server):
        srv, _, _ = server
        assert srv.port > 0
        # Shutdown is driven by the fixture teardown.


class TestGetters:
    def test_gr_invalid_pointing(self, server):
        srv, _, _ = server
        s = _connect(srv)
        s.sendall(b":GR#")
        reply = _recv_until_hash(s)
        assert reply == b"00:00:00#"
        s.close()

    def test_gvp_identity(self, server):
        srv, _, _ = server
        s = _connect(srv)
        s.sendall(b":GVP#")
        reply = _recv_until_hash(s)
        assert reply == b"LX200 Classic#"
        s.close()

    def test_gr_valid_pointing_round_trips(self, server):
        srv, ps, _ = server
        # Vega J2000
        ps.update(ra_j2000=279.234, dec_j2000=38.784, roll=0.0, matches=10, prob=0.01)
        s = _connect(srv)
        s.sendall(b":GR#:GD#")
        buf = b""
        start = time.time()
        while time.time() - start < 2.0 and buf.count(b"#") < 2:
            buf += s.recv(256)
        assert buf.count(b"#") == 2
        ra_reply, _, rest = buf.partition(b"#")
        dec_reply, _, _ = rest.partition(b"#")
        # Just verify format shape — precise value is time-dependent
        assert len(ra_reply) == 8  # HH:MM:SS
        assert ra_reply[2:3] == b":"
        assert ra_reply[5:6] == b":"
        assert len(dec_reply) == 9  # sDD*MM:SS
        assert dec_reply[0:1] in (b"+", b"-")
        s.close()


class TestMultiClientIsolation:
    def test_precision_per_client(self, server):
        srv, ps, _ = server
        ps.update(ra_j2000=90.0, dec_j2000=45.0, roll=0.0, matches=10, prob=0.01)
        a = _connect(srv)
        b = _connect(srv)
        # Client A toggles to low precision
        a.sendall(b":U#:GR#")
        # Client B stays on high precision
        b.sendall(b":GR#")
        ra_a = _recv_until_hash(a)
        ra_b = _recv_until_hash(b)
        # Low precision: HH:MM.T# (8 chars including #)
        # High precision: HH:MM:SS# (9 chars including #)
        assert len(ra_a) == 8
        assert b"." in ra_a
        assert len(ra_b) == 9
        assert ra_b.count(b":") == 2
        a.close()
        b.close()


class TestGoto:
    def test_ms_writes_j2000_to_goto_target(self, server):
        srv, _, gt = server
        s = _connect(srv)
        s.sendall(b":Sr 12:00:00#")
        assert _recv_until_hash(s) == b"1"
        s.sendall(b":Sd +00*00:00#")
        assert _recv_until_hash(s) == b"1"
        s.sendall(b":MS#")
        assert _recv_until_hash(s) == b"0"
        snap = gt.read()
        assert snap.active is True
        # JNow RA=180° precessed back to J2000 should be close to 180° (±2°)
        assert abs(snap.ra_j2000 - 180.0) < 2.0
        assert abs(snap.dec_j2000) < 1.0
        s.close()


class TestMalformedRecovery:
    def test_unknown_commands_do_not_break_stream(self, server):
        srv, _, _ = server
        s = _connect(srv)
        # Mix unknown and known commands; unknown must be silently consumed
        s.sendall(b":ED#:$BDG#:GVP#")
        reply = _recv_until_hash(s)
        assert reply == b"LX200 Classic#"
        s.close()


class TestBufferOverflow:
    def test_oversized_pre_hash_payload_does_not_crash(self, server):
        srv, _, _ = server
        s = _connect(srv)
        # Send 5000 bytes of junk with no '#' terminator, then a valid command
        s.sendall(b"X" * 5000 + b":GVP#")
        reply = _recv_until_hash(s)
        # The overflow should trim without crashing; :GVP# after the trim
        # should still be processed.
        assert reply == b"LX200 Classic#"
        s.close()
