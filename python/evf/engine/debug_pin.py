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

"""Debug mode from a jumper on the Raspberry Pi header (headless only).

A jumper between GPIO21 (pin 40) and GND (pin 39) turns on PushNav's
debug mode, the same as PUSHNAV_DEBUG=1: the Debug panel, sample-image
injection and frame capture.

Run by the pushnav-headless service as root, before PushNav starts:

    ExecStartPre=+... -m evf.engine.debug_pin

It reads GPIO21 once with the internal pull-up on, and creates
DEBUG_FLAG when the pin reads low (jumpered to ground). PushNav checks
for that file at startup; the unit's RuntimeDirectory= removes it when
the service stops. The pin is read through the kernel's GPIO character
device (uAPI v2), so no GPIO library is needed and the sandboxed service
itself gets no GPIO access.

Always exits 0: no GPIO chip, a busy pin or an odd board just leaves
debug mode off. `--check` prints what it sees without touching the flag.
"""

import argparse
import logging
import os
import struct
import sys
import time
from pathlib import Path

logger = logging.getLogger("evf.debug_pin")

DEBUG_GPIO = 21
DEBUG_FLAG = Path("/run/pushnav-headless/debug")

# Labels of the GPIO controller wired to the 40-pin header:
# Pi 5 (RP1), Pi 4, and Pi 3 / Zero 2 W. Header GPIO n is line n on it.
_HEADER_CHIP_LABELS = ("pinctrl-rp1", "pinctrl-bcm2711", "pinctrl-bcm2835")

# -- Linux GPIO uAPI v2 (include/uapi/linux/gpio.h) ---------------------------

_IOC_WRITE, _IOC_READ = 1, 2


def _ioc(direction: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (0xB4 << 8) | nr


_CHIPINFO = struct.Struct("32s32sI")  # struct gpiochip_info
_LINE_VALUES = struct.Struct("QQ")  # struct gpio_v2_line_values: bits, mask
# struct gpio_v2_line_request field offsets: offsets[64] u32, consumer[32],
# config (flags u64, num_attrs u32, padding[5], attrs[10] x 24 bytes),
# num_lines u32, event_buffer_size u32, padding[5], fd s32.
_LINE_REQUEST_SIZE = 592
_OFF_CONSUMER = 256
_OFF_CONFIG_FLAGS = 288
_OFF_NUM_LINES = 560
_OFF_FD = 588

GPIO_GET_CHIPINFO_IOCTL = _ioc(_IOC_READ, 0x01, _CHIPINFO.size)
GPIO_V2_GET_LINE_IOCTL = _ioc(_IOC_READ | _IOC_WRITE, 0x07, _LINE_REQUEST_SIZE)
GPIO_V2_LINE_GET_VALUES_IOCTL = _ioc(_IOC_READ | _IOC_WRITE, 0x0E, _LINE_VALUES.size)

_FLAG_INPUT = 1 << 2
_FLAG_BIAS_PULL_UP = 1 << 8


def _line_request(line: int) -> bytearray:
    """gpio_v2_line_request for one input line with the pull-up on."""
    req = bytearray(_LINE_REQUEST_SIZE)
    struct.pack_into("I", req, 0, line)
    struct.pack_into("32s", req, _OFF_CONSUMER, b"pushnav-debug")
    struct.pack_into("Q", req, _OFF_CONFIG_FLAGS, _FLAG_INPUT | _FLAG_BIAS_PULL_UP)
    struct.pack_into("I", req, _OFF_NUM_LINES, 1)
    return req


def _chip_label(chip: Path) -> str | None:
    import fcntl  # Unix only; keep this module importable on Windows

    try:
        fd = os.open(chip, os.O_RDWR | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        info = bytearray(_CHIPINFO.size)
        fcntl.ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, info)
    except OSError:
        return None
    finally:
        os.close(fd)
    _, label, _ = _CHIPINFO.unpack(info)
    return label.rstrip(b"\0").decode(errors="replace")


def header_chip(dev: Path = Path("/dev")) -> tuple[Path, str] | None:
    """The GPIO chip driving the 40-pin header, and its label."""
    for chip in sorted(dev.glob("gpiochip*")):
        label = _chip_label(chip)
        if label in _HEADER_CHIP_LABELS:
            return chip, label
    return None


def read_jumper(chip: Path, line: int = DEBUG_GPIO) -> bool:
    """True if `line` reads low with the pull-up on, i.e. jumpered to GND."""
    import fcntl

    req = _line_request(line)
    fd = os.open(chip, os.O_RDWR | os.O_CLOEXEC)
    try:
        fcntl.ioctl(fd, GPIO_V2_GET_LINE_IOCTL, req)
    finally:
        os.close(fd)
    (line_fd,) = struct.unpack_from("i", req, _OFF_FD)
    try:
        time.sleep(0.01)  # let the pull-up settle
        values = bytearray(_LINE_VALUES.pack(0, 1))
        fcntl.ioctl(line_fd, GPIO_V2_LINE_GET_VALUES_IOCTL, values)
        bits, _ = _LINE_VALUES.unpack(values)
    finally:
        os.close(line_fd)
    return not bits & 1


def debug_jumper_fitted(dev: Path = Path("/dev")) -> bool:
    found = header_chip(dev)
    return found is not None and read_jumper(found[0])


def debug_flag_set(flag: Path = DEBUG_FLAG) -> bool:
    """True if the service's start step found the debug jumper."""
    return flag.exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evf.engine.debug_pin")
    parser.add_argument("--flag", type=Path, default=DEBUG_FLAG)
    parser.add_argument("--dev", type=Path, default=Path("/dev"))
    parser.add_argument("--check", action="store_true",
                        help="print the chip and pin state; leave the flag alone")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="debug_pin: %(message)s",
                        stream=sys.stderr)
    if args.check:
        found = header_chip(args.dev)
        if found is None:
            print("no 40-pin header GPIO chip found")
        else:
            chip, label = found
            low = read_jumper(chip)
            print(f"{chip} ({label}): GPIO{DEBUG_GPIO} reads "
                  f"{'low: jumper fitted, debug mode on' if low else 'high: no jumper'}")
        return 0
    try:
        if debug_jumper_fitted(args.dev):
            args.flag.parent.mkdir(parents=True, exist_ok=True)
            args.flag.write_text(f"GPIO{DEBUG_GPIO} jumpered to GND\n")
            logger.info("GPIO%d is jumpered to GND: debug mode on", DEBUG_GPIO)
        else:
            args.flag.unlink(missing_ok=True)
    except Exception as exc:  # never block the service
        logger.warning("could not read GPIO%d, debug mode off: %s", DEBUG_GPIO, exc)
        try:
            args.flag.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
