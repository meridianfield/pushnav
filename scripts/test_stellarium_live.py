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

"""Standalone Stellarium server test — broadcasts a fixed star position."""

import sys
import time

from evf.engine.pointing import PointingState
from evf.stellarium.server import StellariumServer

TARGETS = {
    "vega":       (279.23,  +38.78, "Vega (Lyra) — RA 18h37m, Dec +38°47'"),
    "sirius":     (101.29,  -16.72, "Sirius (CMa) — RA 6h45m, Dec -16°43'"),
    "polaris":    ( 37.95,  +89.26, "Polaris (UMi) — RA 2h32m, Dec +89°16'"),
    "canopus":    ( 95.99,  -52.70, "Canopus (Car) — RA 6h24m, Dec -52°42'"),
    "betelgeuse": ( 88.79,   +7.41, "Betelgeuse (Ori) — RA 5h55m, Dec +7°24'"),
    "achernar":   ( 24.43,  -57.24, "Achernar (Eri) — RA 1h38m, Dec -57°14'"),
}

name = sys.argv[1].lower() if len(sys.argv) > 1 else "vega"
if name not in TARGETS:
    print(f"Unknown target. Choose from: {', '.join(TARGETS)}")
    sys.exit(1)

ra_deg, dec_deg, label = TARGETS[name]

pointing = PointingState()
pointing.update(ra_j2000=ra_deg, dec_j2000=dec_deg, roll=0.0, matches=10, prob=0.05)

server = StellariumServer(pointing, port=10001)
server.start()

print(f"Broadcasting: {label}")
print(f"  RA={ra_deg}°  Dec={dec_deg}°  on localhost:10001")
print("Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    server.stop()
    print("Stopped.")
