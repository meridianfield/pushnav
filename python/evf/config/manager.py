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

"""Configuration manager — JSON persistence with defaults and versioning."""

import json
import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_VERSION = 1

DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "solver": {"min_matches": 8, "max_prob": 0.2},
    "camera": {"exposure": 100, "gain": 10},
    "calibration": {"finder_rotation": 0.0, "sync_d_body": None},
    "logging": {"verbose": False},
    "audio": {"enabled": True},
    "display": {"hidpi": False},
    "webserver": {"port": 8080},
}


def _default_config_dir() -> Path:
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "ElectronicViewfinder"
    if platform.system() == "Linux":
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg) / "electronic-viewfinder"
    return Path.home() / "Library" / "Application Support" / "ElectronicViewfinder"


_DEFAULT_DIR = _default_config_dir()


class ConfigManager:
    """Load, save, and access application configuration.

    Config path: ~/Library/Application Support/ElectronicViewfinder/config.json
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or _DEFAULT_DIR
        self._path = self._dir / "config.json"
        self._data: dict = {}
        self._dirty = False
        self._load()

    # -- persistence ----------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._data = json.load(f)
                if self._data.get("version") != CONFIG_VERSION:
                    logger.warning(
                        "Config version mismatch (got %s, expected %s) — using defaults",
                        self._data.get("version"),
                        CONFIG_VERSION,
                    )
                    self._data = _deep_copy(DEFAULT_CONFIG)
                    self._dirty = True
                else:
                    # Merge in any missing keys from defaults
                    self._data = _merge_defaults(DEFAULT_CONFIG, self._data)
                logger.info("Loaded config from %s", self._path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to read config (%s) — using defaults", exc)
                self._data = _deep_copy(DEFAULT_CONFIG)
                self._dirty = True
        else:
            logger.info("No config file found — creating defaults at %s", self._path)
            self._data = _deep_copy(DEFAULT_CONFIG)
            self._dirty = True
        if self._dirty:
            self.save()

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)
            f.write("\n")
        self._dirty = False
        logger.debug("Config saved to %s", self._path)

    # -- getters / setters ----------------------------------------------------

    def get(self, section: str, key: str):
        return self._data.get(section, {}).get(key)

    def set(self, section: str, key: str, value) -> None:
        if section not in self._data:
            self._data[section] = {}
        if self._data[section].get(key) != value:
            self._data[section][key] = value
            self._dirty = True
            self.save()

    # -- convenience properties -----------------------------------------------

    @property
    def min_matches(self) -> int:
        return self.get("solver", "min_matches")

    @min_matches.setter
    def min_matches(self, value: int) -> None:
        self.set("solver", "min_matches", value)

    @property
    def max_prob(self) -> float:
        return self.get("solver", "max_prob")

    @max_prob.setter
    def max_prob(self, value: float) -> None:
        self.set("solver", "max_prob", value)

    @property
    def exposure(self) -> int:
        return self.get("camera", "exposure")

    @exposure.setter
    def exposure(self, value: int) -> None:
        self.set("camera", "exposure", value)

    @property
    def gain(self) -> int:
        return self.get("camera", "gain")

    @gain.setter
    def gain(self, value: int) -> None:
        self.set("camera", "gain", value)

    @property
    def finder_rotation(self) -> float:
        return self.get("calibration", "finder_rotation")

    @finder_rotation.setter
    def finder_rotation(self, value: float) -> None:
        self.set("calibration", "finder_rotation", value)

    @property
    def sync_d_body(self) -> list[float] | None:
        return self.get("calibration", "sync_d_body")

    @sync_d_body.setter
    def sync_d_body(self, value: list[float] | None) -> None:
        self.set("calibration", "sync_d_body", value)

    @property
    def has_calibration(self) -> bool:
        """True if both sync_d_body and finder_rotation have been saved."""
        return self.sync_d_body is not None

    @property
    def audio_enabled(self) -> bool:
        return self.get("audio", "enabled")

    @audio_enabled.setter
    def audio_enabled(self, value: bool) -> None:
        self.set("audio", "enabled", value)

    @property
    def hidpi(self) -> bool:
        return self.get("display", "hidpi")

    @hidpi.setter
    def hidpi(self, value: bool) -> None:
        self.set("display", "hidpi", value)

    @property
    def verbose(self) -> bool:
        return self.get("logging", "verbose")

    @verbose.setter
    def verbose(self, value: bool) -> None:
        self.set("logging", "verbose", value)

    @property
    def web_port(self) -> int:
        return self.get("webserver", "port")

    @web_port.setter
    def web_port(self, value: int) -> None:
        if not (1024 <= value <= 65535):
            raise ValueError(f"Web port must be between 1024 and 65535, got {value}")
        self.set("webserver", "port", value)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def data(self) -> dict:
        return _deep_copy(self._data)


def _deep_copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def _merge_defaults(defaults: dict, current: dict) -> dict:
    """Recursively merge missing keys from defaults into current."""
    merged = dict(current)
    for key, default_val in defaults.items():
        if key not in merged:
            merged[key] = _deep_copy(default_val) if isinstance(default_val, dict) else default_val
        elif isinstance(default_val, dict) and isinstance(merged[key], dict):
            merged[key] = _merge_defaults(default_val, merged[key])
    return merged
