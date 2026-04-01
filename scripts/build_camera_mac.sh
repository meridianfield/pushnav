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

# Build the macOS camera server (Swift) and copy the binary to camera/mac/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CAMERA_DIR="$PROJECT_ROOT/camera/mac"

echo "Building camera_server..."
cd "$CAMERA_DIR"
swift build -c release

# Copy binary to camera/mac/ for easy access
BUILD_BIN="$(swift build -c release --show-bin-path)/camera_server"
cp "$BUILD_BIN" "$CAMERA_DIR/camera_server"

echo "Build complete: $CAMERA_DIR/camera_server"
