# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Known camera/lens plate-solving profiles, selected by USB VID/PID."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraProfile:
    label: str
    database_filename: str
    fov_estimate_deg: float
    fov_max_error_deg: float


DEFAULT_CAMERA_PROFILE = CameraProfile(
    label="OV9281 with 25 mm lens",
    database_filename="tetra3rs_gaia.bin",
    fov_estimate_deg=8.86,
    fov_max_error_deg=1.5,
)

_DFROBOT_IMX662_25MM = CameraProfile(
    label="DFRobot IMX662 with 25 mm lens",
    database_filename="tetra3rs_gaia_imx662_25mm.bin",
    fov_estimate_deg=12.7,
    fov_max_error_deg=2.0,
)

_PROFILES_BY_CAMERA_ID = {
    "1bcf:2d4f": _DFROBOT_IMX662_25MM,
}


def camera_profile_for_id(camera_id: str | None) -> CameraProfile:
    """Return the known profile for a normalized USB ``vid:pid`` string.

    Missing or unknown IDs preserve the original OV9281 behavior. This keeps
    protocol-v1 compatibility with older camera servers and user-configured
    cameras whose lens geometry is not known to PushNav.
    """
    if camera_id is None:
        return DEFAULT_CAMERA_PROFILE
    return _PROFILES_BY_CAMERA_ID.get(
        camera_id.strip().lower(), DEFAULT_CAMERA_PROFILE
    )
