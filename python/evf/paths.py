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

"""Centralized path resolution for dev mode (repo) vs release mode (.app bundle).

Dev mode:   repo root found by walking up from __file__ to pyproject.toml
Release:    sys.executable sits inside Contents/MacOS/ -> Resources at ../../Resources/
"""

import platform
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

_exe = Path(sys.executable).resolve()
_BUNDLE_MODE = _exe.parent.name == "MacOS" and _exe.parent.parent.name == "Contents"
_LINUX_RELEASE = (
    not _BUNDLE_MODE
    and platform.system() == "Linux"
    and (_exe.parent / "data" / "VERSION.json").exists()
)
_WINDOWS_RELEASE = (
    not _BUNDLE_MODE
    and platform.system() == "Windows"
    and (_exe.parent / "data" / "VERSION.json").exists()
)

if _BUNDLE_MODE:
    _CONTENTS = _exe.parent.parent
    _MACOS = _CONTENTS / "MacOS"
    _RESOURCES = _CONTENTS / "Resources"
    _RELEASE_ROOT = None
    _REPO_ROOT = None
elif _LINUX_RELEASE or _WINDOWS_RELEASE:
    _RELEASE_ROOT = _exe.parent
    _CONTENTS = None
    _MACOS = None
    _RESOURCES = None
    _REPO_ROOT = None
else:
    # Walk up from this file to find pyproject.toml
    _d = Path(__file__).resolve().parent
    while _d != _d.parent:
        if (_d / "pyproject.toml").exists():
            break
        _d = _d.parent
    _REPO_ROOT = _d
    _RELEASE_ROOT = None
    _CONTENTS = None
    _MACOS = None
    _RESOURCES = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def database_path() -> Path:
    """Path to tetra3 star database (without .npz extension for tetra3 API)."""
    if _BUNDLE_MODE:
        return _RESOURCES / "hip8_database"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "hip8_database"
    return _REPO_ROOT / "data" / "hip8_database"


def version_json() -> Path:
    if _BUNDLE_MODE:
        return _RESOURCES / "VERSION.json"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "VERSION.json"
    return _REPO_ROOT / "data" / "VERSION.json"


def sounds_dir() -> Path:
    if _BUNDLE_MODE:
        return _RESOURCES / "sounds"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "sounds"
    return _REPO_ROOT / "data" / "sounds"


def fonts_dir() -> Path:
    if _BUNDLE_MODE:
        return _RESOURCES / "fonts"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "fonts"
    return _REPO_ROOT / "data" / "fonts"


def title_image() -> Path:
    if _BUNDLE_MODE:
        return _RESOURCES / "marketing" / "inapp-title.png"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "marketing" / "inapp-title.png"
    return _REPO_ROOT / "marketing" / "inapp-title.png"


def camera_binary() -> Path:
    """Path to the camera server binary/script.

    On macOS bundle: compiled Swift binary inside .app
    On Linux release: compiled C binary next to evf executable
    On Windows release: compiled C binary next to evf executable
    On Linux dev: compiled C binary at camera/linux/camera_server
    On Windows dev: compiled C binary at camera/windows/camera_server.exe
    On macOS dev: compiled Swift binary at camera/mac/camera_server

    Raises FileNotFoundError if the binary/script cannot be located.
    """
    if _BUNDLE_MODE:
        p = _MACOS / "camera_server"
        if p.exists():
            return p
        raise FileNotFoundError("Cannot find camera_server in .app bundle")
    if _LINUX_RELEASE:
        p = _RELEASE_ROOT / "camera_server"
        if p.exists():
            return p
        raise FileNotFoundError(f"Cannot find camera_server at {p}")
    if _WINDOWS_RELEASE:
        p = _RELEASE_ROOT / "camera_server.exe"
        if p.exists():
            return p
        raise FileNotFoundError(f"Cannot find camera_server.exe at {p}")
    if platform.system() == "Linux":
        p = _REPO_ROOT / "camera" / "linux" / "camera_server"
        if p.exists():
            return p
        raise FileNotFoundError(
            f"Cannot find camera_server at {p} — run make -C camera/linux"
        )
    if platform.system() == "Windows":
        p = _REPO_ROOT / "camera" / "windows" / "camera_server.exe"
        if p.exists():
            return p
        raise FileNotFoundError(
            f"Cannot find camera_server.exe at {p} — run camera\\windows\\build.bat"
        )
    p = _REPO_ROOT / "camera" / "mac" / "camera_server"
    if p.exists():
        return p
    raise FileNotFoundError(
        f"Cannot find camera_server at {p} — run scripts/build_camera_mac.sh"
    )


def web_dir() -> Path:
    """Path to data/web/ directory (mobile web interface assets)."""
    if _BUNDLE_MODE:
        return _RESOURCES / "web"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "web"
    return _REPO_ROOT / "data" / "web"


def samples_dir() -> Path | None:
    """Path to test sample images. Returns None in release modes (not shipped)."""
    if _BUNDLE_MODE or _LINUX_RELEASE or _WINDOWS_RELEASE:
        return None
    return _REPO_ROOT / "tests" / "samples"
