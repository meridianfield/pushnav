# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Camera/lens profile selection tests."""

from evf.camera.profile import DEFAULT_CAMERA_PROFILE, camera_profile_for_id


def test_dfrobot_imx662_uses_25mm_profile():
    profile = camera_profile_for_id("1BCF:2D4F")

    assert profile.database_filename == "tetra3rs_gaia_imx662_25mm.bin"
    assert profile.fov_estimate_deg == 12.7
    assert profile.fov_max_error_deg == 2.0


def test_missing_camera_id_preserves_original_profile():
    assert camera_profile_for_id(None) is DEFAULT_CAMERA_PROFILE


def test_unknown_camera_id_preserves_original_profile():
    assert camera_profile_for_id("ffff:ffff") is DEFAULT_CAMERA_PROFILE
