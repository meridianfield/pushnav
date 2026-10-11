"""PUSHNAV_ROOT (pushnav-headless launcher) resolves paths into the install root.

evf.paths resolves at import time, so each case runs in a fresh interpreter.
"""

import json
import os
import platform
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    platform.system() != "Linux", reason="PUSHNAV_ROOT is a Linux headless install"
)

_PROBE = """
import json
from evf import paths
try:
    camera = str(paths.camera_binary())
except FileNotFoundError as exc:  # repo checkout without a built camera_server
    camera = str(exc)
print(json.dumps({
    "db": str(paths.tetra3rs_database_path()),
    "version": str(paths.version_json()),
    "sounds": str(paths.sounds_dir()),
    "title": str(paths.title_image()),
    "camera": camera,
    "web": str(paths.web_dist_dir()),
    "samples": str(paths.samples_dir()),
}))
"""


def _resolve(env_root: str | None) -> dict:
    env = dict(os.environ)
    env.pop("PUSHNAV_ROOT", None)
    if env_root is not None:
        env["PUSHNAV_ROOT"] = env_root
    out = subprocess.run(
        [sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def test_pushnav_root_uses_release_layout(tmp_path):
    root = tmp_path / "pushnav-headless"
    (root / "data" / "samples").mkdir(parents=True)
    (root / "camera_server").touch()
    p = _resolve(str(root))
    assert p == {
        "db": str(root / "data" / "tetra3rs_gaia.bin"),
        "version": str(root / "data" / "VERSION.json"),
        "sounds": str(root / "data" / "sounds"),
        "title": str(root / "marketing" / "inapp-title.png"),
        "camera": str(root / "camera_server"),
        "web": str(root / "data" / "web_dist"),
        "samples": str(root / "data" / "samples"),
    }


def test_without_pushnav_root_stays_in_repo(tmp_path):
    p = _resolve(None)
    assert "camera/linux/camera_server" in p["camera"]
    assert p["web"].endswith("web/dist")
