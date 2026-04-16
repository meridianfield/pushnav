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

"""J2000 <-> JNow precession using pyerfa (IAU 2006).

PushNav's internal canonical form is J2000 (ICRS — what tetra3 plate-solver
returns against the hip_main catalog). LX200 clients (SkySafari, Stellarium
Mobile, ASCOM Meade Generic, INDI lx200basic) expect JNow — mean equinox
of date, precession only, no nutation, no aberration.

We apply precession only (matches SkySafari's expectation of "mean equinox
of date"). The precession matrix is cached for 60 seconds since it changes
by microarcseconds over that interval; this removes any per-poll cost
concern on embedded hardware.

Note on UTC->TT conversion: we hardcode the offset as 69.184 s
(37 leap seconds + 32.184 s TAI->TT) as of 2026. A future leap second
would introduce at most ~15 mas of precession error — negligible for
arc-minute push-to precision.
"""

import threading
import time

import erfa
import numpy as np

_CACHE_SECONDS = 60.0
_lock = threading.Lock()
_cached_matrix: np.ndarray | None = None
_cached_transpose: np.ndarray | None = None
_cached_at: float = 0.0


def _unix_to_jd_tt(unix_seconds: float) -> tuple[float, float]:
    """Convert Unix time (UTC) to a two-part Julian Date in TT.

    Two-part form preserves precision (erfa convention).
    """
    jd1 = 2440587.5  # JD of Unix epoch (1970-01-01 00:00 UTC)
    jd2 = unix_seconds / 86400.0 + 69.184 / 86400.0
    return jd1, jd2


def _refresh_matrix() -> tuple[np.ndarray, np.ndarray]:
    """Return (P, P.T); regenerate if older than _CACHE_SECONDS."""
    global _cached_matrix, _cached_transpose, _cached_at
    now = time.time()
    with _lock:
        if _cached_matrix is None or (now - _cached_at) > _CACHE_SECONDS:
            jd1, jd2 = _unix_to_jd_tt(now)
            P = erfa.pmat06(jd1, jd2)  # IAU 2006 precession matrix
            _cached_matrix = P
            _cached_transpose = P.T  # rotation -> inverse == transpose
            _cached_at = now
        return _cached_matrix, _cached_transpose


def _radec_to_vec(ra_deg: float, dec_deg: float) -> np.ndarray:
    ra = np.deg2rad(ra_deg)
    dec = np.deg2rad(dec_deg)
    cd = np.cos(dec)
    return np.array([cd * np.cos(ra), cd * np.sin(ra), np.sin(dec)])


def _vec_to_radec(v: np.ndarray) -> tuple[float, float]:
    ra = np.rad2deg(np.arctan2(v[1], v[0])) % 360.0
    dec = np.rad2deg(np.arcsin(np.clip(v[2], -1.0, 1.0)))
    return ra, dec


def j2000_to_jnow(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    """J2000 (ICRS) -> mean equinox of date. Returns (ra_deg, dec_deg)."""
    P, _ = _refresh_matrix()
    return _vec_to_radec(P @ _radec_to_vec(ra_deg, dec_deg))


def jnow_to_j2000(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    """Mean equinox of date -> J2000 (ICRS). Returns (ra_deg, dec_deg)."""
    _, Pt = _refresh_matrix()
    return _vec_to_radec(Pt @ _radec_to_vec(ra_deg, dec_deg))
