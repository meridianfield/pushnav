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

"""Root helper that hands the Pi's LEDs to PushNav and gives them back.

Run by the pushnav-headless service as root, outside its sandbox:

    ExecStartPre=+... -m evf.engine.led_helper take --group pushnav
    ExecStopPost=+... -m evf.engine.led_helper restore

`take` saves each LED's trigger, brightness and file ownership to /run
(tmpfs, so it never outlives a boot), sets trigger=none and lets the
group write `brightness`. `restore` puts everything back. ExecStopPost
also runs after a crash, so the LEDs never stay frozen on a PushNav
pattern.

Both commands always exit 0: a missing or odd LED must never stop
PushNav from starting.

For development on the Pi: `sudo uv run python -m evf.engine.led_helper
take --group "$(id -gn)"`, and `restore` when done.
"""

import argparse
import grp
import json
import logging
import os
import stat
import sys
from pathlib import Path

from evf.config.manager import _default_config_dir
from evf.engine.status_led import _LED_NAMES, LEDS_SYSFS

logger = logging.getLogger("evf.led_helper")

STATE_DIR = Path("/run/pushnav-headless-led")


def led_enabled(config_path: Path) -> bool:
    """`led.enabled` from config.json; missing or unreadable means the default (on).

    Read-only on purpose: this runs as root and must never create or
    rewrite the service user's config file.
    """
    try:
        with open(config_path) as f:
            value = json.load(f).get("led", {}).get("enabled", True)
    except (OSError, ValueError, AttributeError):
        return True
    return value is not False


def _present_leds(root: Path) -> list[Path]:
    """One directory per colour, preferring the current kernel names."""
    found = []
    for names in _LED_NAMES.values():
        for name in names:
            if (root / name / "brightness").exists():
                found.append(root / name)
                break
    return found


def _current_trigger(led: Path) -> str:
    # e.g. "none timer [mmc0] heartbeat" -> "mmc0"
    for word in (led / "trigger").read_text().split():
        if word.startswith("[") and word.endswith("]"):
            return word[1:-1]
    return "none"


def take(root: Path, state_dir: Path, group: str) -> None:
    gid = grp.getgrnam(group).gr_gid
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for led in _present_leds(root):
        try:
            _take_one(led, state_dir, gid)
            logger.info("%s: taken (trigger=none, writable by group %s)", led.name, group)
        except (OSError, ValueError) as exc:
            logger.warning("%s: take failed: %s", led.name, exc)


def _take_one(led: Path, state_dir: Path, gid: int) -> None:
    brightness = led / "brightness"
    saved = state_dir / f"{led.name}.json"
    # Keep the first saved state: a second `take` (restart without a
    # restore in between) would otherwise record our own "none".
    if not saved.exists():
        st = brightness.stat()
        saved.write_text(json.dumps({
            "trigger": _current_trigger(led),
            "brightness": int(brightness.read_text().strip() or 0),
            "uid": st.st_uid,
            "gid": st.st_gid,
            "mode": stat.S_IMODE(st.st_mode),
        }))
    (led / "trigger").write_text("none")
    brightness.write_text("0")
    os.chown(brightness, -1, gid)
    os.chmod(brightness, stat.S_IMODE(brightness.stat().st_mode) | stat.S_IWGRP)


def restore(root: Path, state_dir: Path) -> None:
    if not state_dir.is_dir():
        return
    for saved in sorted(state_dir.glob("*.json")):
        led = root / saved.stem
        try:
            s = json.loads(saved.read_text())
            brightness = led / "brightness"
            os.chown(brightness, s["uid"], s["gid"])
            os.chmod(brightness, s["mode"])
            brightness.write_text(str(s["brightness"]))
            # Trigger last: e.g. mmc0 takes the LED over from here.
            (led / "trigger").write_text(s["trigger"])
            logger.info("%s: restored (trigger=%s)", led.name, s["trigger"])
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("%s: restore failed: %s", led.name, exc)
        saved.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evf.engine.led_helper")
    parser.add_argument("action", choices=["take", "restore"])
    parser.add_argument("--group", default="pushnav")
    parser.add_argument("--root", type=Path, default=LEDS_SYSFS)
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR)
    parser.add_argument("--config", type=Path,
                        default=_default_config_dir() / "config.json")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="led_helper: %(message)s",
                        stream=sys.stderr)
    try:
        if args.action == "take":
            if not led_enabled(args.config):
                logger.info("led.enabled is false in %s; leaving the LEDs alone",
                            args.config)
            else:
                take(args.root, args.state_dir, args.group)
        else:
            restore(args.root, args.state_dir)
    except Exception as exc:  # never block the service
        logger.warning("%s failed: %s", args.action, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
