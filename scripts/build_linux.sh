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

# Build PushNav Linux release (tar.gz + AppImage)
# Usage: ./scripts/build_linux.sh
#
# Prerequisites:
#   sudo apt install gcc libjpeg-dev libfuse2
#   uv, python3, nuitka
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$REPO_ROOT/build"
APP_NAME="PushNav-linux"
APP_DIR="$BUILD_DIR/$APP_NAME"

echo "==> Cleaning previous build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# -------------------------------------------------------------------------
# Phase 1: Build C camera server
# -------------------------------------------------------------------------
echo "==> Building C camera server"
make -C "$REPO_ROOT/camera/linux" clean
make -C "$REPO_ROOT/camera/linux"
CAMERA_BIN="$REPO_ROOT/camera/linux/camera_server"
if [ ! -f "$CAMERA_BIN" ]; then
    echo "ERROR: camera_server not found at $CAMERA_BIN"
    exit 1
fi
echo "    Camera server: $(du -h "$CAMERA_BIN" | cut -f1)"

# -------------------------------------------------------------------------
# Phase 2: Build Python with Nuitka (standalone)
# -------------------------------------------------------------------------
echo "==> Building Python app with Nuitka (standalone)"
uv run python -m nuitka \
    --standalone \
    --output-dir="$BUILD_DIR" \
    --output-filename=evf \
    --include-package=dearpygui \
    --include-package=numpy \
    --include-package=scipy \
    --include-package=PIL \
    --include-package=playsound3 \
    --include-package=tetra3 \
    --nofollow-import-to=pytest \
    --nofollow-import-to=setuptools \
    --nofollow-import-to=linuxpy \
    --nofollow-import-to=_tkinter \
    --assume-yes-for-downloads \
    "$REPO_ROOT/python/evf/main.py"

NUITKA_DIST="$BUILD_DIR/main.dist"
if [ ! -d "$NUITKA_DIST" ]; then
    echo "ERROR: Nuitka dist not found at $NUITKA_DIST"
    exit 1
fi

# -------------------------------------------------------------------------
# Phase 3: Assemble release directory
# -------------------------------------------------------------------------
echo "==> Assembling $APP_NAME"
mkdir -p "$APP_DIR/data" "$APP_DIR/marketing"

# Copy Nuitka standalone dist
cp -a "$NUITKA_DIST"/* "$APP_DIR/"

# Copy C camera server binary
cp "$CAMERA_BIN" "$APP_DIR/camera_server"
chmod +x "$APP_DIR/camera_server"

# Copy data resources
cp "$REPO_ROOT/data/hip8_database.npz" "$APP_DIR/data/"
cp "$REPO_ROOT/data/VERSION.json" "$APP_DIR/data/"
cp -a "$REPO_ROOT/data/sounds" "$APP_DIR/data/sounds"
cp -a "$REPO_ROOT/data/fonts" "$APP_DIR/data/fonts"

# Copy marketing assets
cp "$REPO_ROOT/marketing/inapp-title.png" "$APP_DIR/marketing/"

echo "==> Release directory assembled at $APP_DIR"

# -------------------------------------------------------------------------
# Phase 4: Create tar.gz
# -------------------------------------------------------------------------
ARCH="$(uname -m)"
TAR_NAME="PushNav-linux-${ARCH}.tar.gz"
TAR_PATH="$BUILD_DIR/$TAR_NAME"
echo "==> Creating $TAR_NAME"
tar czf "$TAR_PATH" -C "$BUILD_DIR" "$APP_NAME"

# -------------------------------------------------------------------------
# Phase 5: Build AppImage
# -------------------------------------------------------------------------
echo "==> Building AppImage"

APPDIR="$BUILD_DIR/PushNav.AppDir"
rm -rf "$APPDIR"

# Copy entire release directory into AppDir
cp -a "$APP_DIR" "$APPDIR"

# Add AppImage metadata
cp "$REPO_ROOT/linux/pushnav.desktop" "$APPDIR/pushnav.desktop"
cp "$REPO_ROOT/marketing/logo.png" "$APPDIR/pushnav.png"

# Bundle libjpeg for camera_server
LIBJPEG="$(ldd "$APPDIR/camera_server" | grep libjpeg | awk '{print $3}')"
if [ -n "$LIBJPEG" ]; then
    cp "$LIBJPEG" "$APPDIR/"
    echo "    Bundled: $LIBJPEG"
fi

# Create AppRun entry point
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="${HERE}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "${HERE}/evf" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# Download appimagetool if not present
APPIMAGETOOL="$BUILD_DIR/appimagetool"
if [ ! -x "$APPIMAGETOOL" ]; then
    ARCH_DL="$(uname -m)"
    echo "    Downloading appimagetool for $ARCH_DL..."
    curl -sSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH_DL}.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

APPIMAGE_PATH="$BUILD_DIR/PushNav-${ARCH}.AppImage"
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_PATH"

echo "==> Build complete!"
echo "    Dir:       $APP_DIR"
echo "    Tar:       $TAR_PATH  ($(du -h "$TAR_PATH" | cut -f1))"
echo "    AppImage:  $APPIMAGE_PATH  ($(du -h "$APPIMAGE_PATH" | cut -f1))"
