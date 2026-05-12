"""PUSHNAV_TESTDATE override for the engine's notion of "astronomical now".

Internal/undocumented feature: when the env var is set, the engine reports
that value (converted to UTC) in every state payload as `astro_now_iso`,
and the React UI uses it in place of `new Date()` for the Sky View dome
alt/az and the What to See catalog's evaluation time. Wall-clock-bound
behaviour (solve_age_s, log timestamps, server cadences, etc.) is *not*
affected — see comment in `astro_now_iso` below.

When the env var is unset, `init_test_date()` is a no-op, `astro_now_iso()`
returns None, and the frontend falls back to the real clock.

Format accepted:
- ``YYYY-MM-DD HH:MM`` or ``YYYY-MM-DDTHH:MM``  → system local time
- Append ``Z`` (e.g. ``2026-04-15T22:00Z``)     → explicit UTC

Invalid formats raise ValueError at startup so the operator sees the
problem immediately rather than silently getting wrong dates.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

_test_date_utc: datetime | None = None


def init_test_date() -> str | None:
    """Parse ``$PUSHNAV_TESTDATE`` once at startup.

    Returns the parsed UTC ISO string if the variable was set, or None
    if it wasn't (in which case the engine stays on the real clock).
    Raises ValueError if the value is malformed.
    """
    global _test_date_utc
    raw = os.environ.get("PUSHNAV_TESTDATE")
    if raw is None or raw.strip() == "":
        _test_date_utc = None
        return None

    s = raw.strip().replace(" ", "T")
    explicit_utc = s.endswith("Z")
    if explicit_utc:
        s = s[:-1]

    try:
        dt_naive = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(
            f"PUSHNAV_TESTDATE={raw!r} is not a valid date/time. "
            f"Use 'YYYY-MM-DD HH:MM' (local time) or append 'Z' for UTC."
        ) from exc

    if explicit_utc:
        dt_utc = dt_naive.replace(tzinfo=timezone.utc)
    else:
        # Treat naive value as local time, then convert to UTC.
        dt_utc = dt_naive.astimezone().astimezone(timezone.utc)

    _test_date_utc = dt_utc
    return dt_utc.isoformat()


def astro_now_iso() -> str | None:
    """ISO UTC string when an override is active, else None.

    The payload builder emits this on every state push; the frontend
    treats None as "use the real Date()" so an unset env var is a true
    no-op (no behavioural change anywhere).
    """
    if _test_date_utc is None:
        return None
    return _test_date_utc.isoformat()


def is_active() -> bool:
    """True iff PUSHNAV_TESTDATE was set and parsed at startup."""
    return _test_date_utc is not None
