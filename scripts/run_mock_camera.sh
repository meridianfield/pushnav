#!/usr/bin/env bash
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

# Start the mock camera server (no real camera needed).
# Streams sample PNG images as MJPEG frames on localhost:8764.
# The Python app can connect to it as if it were a real camera.
set -euo pipefail

cd "$(dirname "$0")/.."
uv run python -m tests.mock_camera_server
