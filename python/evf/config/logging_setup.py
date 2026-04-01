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

"""Logging system — rotating file handler + optional console output."""

import logging
import logging.handlers
import os
import platform
from pathlib import Path


def _default_log_dir() -> Path:
    if platform.system() == "Windows":
        localappdata = os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )
        return Path(localappdata) / "ElectronicViewfinder" / "logs"
    if platform.system() == "Linux":
        xdg = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
        return Path(xdg) / "electronic-viewfinder" / "logs"
    return Path.home() / "Library" / "Application Support" / "ElectronicViewfinder" / "logs"


_DEFAULT_LOG_DIR = _default_log_dir()

LOG_FILE = "evf.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3

_FORMAT = "%(asctime)s %(name)s [%(levelname)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    verbose: bool = False,
    console: bool = False,
    log_dir: Path | None = None,
) -> None:
    """Configure the root logger with a rotating file handler.

    Args:
        verbose: If True, set level to DEBUG; otherwise INFO.
        console: If True, also add a StreamHandler (for dev mode).
        log_dir: Override the default log directory (for testing).
    """
    log_dir = log_dir or _DEFAULT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (allows re-calling for config changes)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Optional console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    logging.getLogger(__name__).debug("Logging initialised (verbose=%s)", verbose)
