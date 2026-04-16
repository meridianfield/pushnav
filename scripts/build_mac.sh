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

# Build PushNav.app macOS bundle + .dmg
# Usage: ./scripts/build_mac.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$REPO_ROOT/build"
APP_NAME="PushNav"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

# Read version from VERSION.json (single source of truth)
APP_VERSION="$(python3 -c "import json; print(json.load(open('$REPO_ROOT/data/VERSION.json'))['app_version'])")"
echo "==> Version: $APP_VERSION"

echo "==> Cleaning previous build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# -------------------------------------------------------------------------
# Phase 1: Build Swift camera server
# -------------------------------------------------------------------------
echo "==> Building Swift camera server"
"$SCRIPT_DIR/build_camera_mac.sh"
CAMERA_BIN="$REPO_ROOT/camera/mac/camera_server"
if [ ! -f "$CAMERA_BIN" ]; then
    echo "ERROR: camera_server not found at $CAMERA_BIN"
    exit 1
fi

# -------------------------------------------------------------------------
# Phase 2: Build Python with Nuitka (standalone)
# -------------------------------------------------------------------------
echo "==> Building Python app with Nuitka (standalone)"
uv run python -m nuitka \
    --standalone \
    --static-libpython=no \
    --output-dir="$BUILD_DIR" \
    --output-filename=evf \
    --include-package=dearpygui \
    --include-package=numpy \
    --include-package=scipy \
    --include-package=PIL \
    --include-package=playsound3 \
    --include-package=tetra3 \
    --include-package=erfa \
    --nofollow-import-to=pytest \
    --nofollow-import-to=setuptools \
    `# Exclude stdlib C extensions that link to Homebrew dylibs — Nuitka 4.x` \
    `# bug: its macOS dep scanner finds them but the DLL inclusion phase` \
    `# doesn't bundle them, causing a FATAL in fixupBinaryDLLPathsMacOS.` \
    `# None of these are needed by this app (DearPyGui + tetra3).` \
    --nofollow-import-to=_blake2 \
    --nofollow-import-to=_hashlib \
    --nofollow-import-to=_ssl \
    --nofollow-import-to=_curses \
    --nofollow-import-to=_curses_panel \
    --nofollow-import-to=_dbm \
    --nofollow-import-to=_gdbm \
    --nofollow-import-to=_tkinter \
    --nofollow-import-to=readline \
    --assume-yes-for-downloads \
    "$REPO_ROOT/python/evf/main.py"

NUITKA_DIST="$BUILD_DIR/main.dist"
if [ ! -d "$NUITKA_DIST" ]; then
    echo "ERROR: Nuitka dist not found at $NUITKA_DIST"
    exit 1
fi

# -------------------------------------------------------------------------
# Phase 2b: Generate app icon (.icns)
# -------------------------------------------------------------------------
echo "==> Generating app icon"
LOGO="$REPO_ROOT/marketing/logo.png"
ICONSET="$BUILD_DIR/AppIcon.iconset"
mkdir -p "$ICONSET"

sips -z   16   16 "$LOGO" --out "$ICONSET/icon_16x16.png"      >/dev/null
sips -z   32   32 "$LOGO" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null
sips -z   32   32 "$LOGO" --out "$ICONSET/icon_32x32.png"      >/dev/null
sips -z   64   64 "$LOGO" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null
sips -z  128  128 "$LOGO" --out "$ICONSET/icon_128x128.png"    >/dev/null
sips -z  256  256 "$LOGO" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z  256  256 "$LOGO" --out "$ICONSET/icon_256x256.png"    >/dev/null
sips -z  512  512 "$LOGO" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z  512  512 "$LOGO" --out "$ICONSET/icon_512x512.png"    >/dev/null
sips -z 1024 1024 "$LOGO" --out "$ICONSET/icon_512x512@2x.png" >/dev/null

iconutil --convert icns "$ICONSET" --output "$BUILD_DIR/AppIcon.icns"
rm -rf "$ICONSET"
echo "    Icon: $BUILD_DIR/AppIcon.icns"

# -------------------------------------------------------------------------
# Phase 3: Assemble .app bundle
# -------------------------------------------------------------------------
echo "==> Assembling $APP_NAME.app"
mkdir -p "$MACOS" "$RESOURCES"

# Copy Nuitka standalone dist into MacOS/
cp -a "$NUITKA_DIST"/* "$MACOS/"

# Copy camera binary
cp "$CAMERA_BIN" "$MACOS/camera_server"
chmod +x "$MACOS/camera_server"

# Copy resources
cp "$REPO_ROOT/data/hip8_database.npz" "$RESOURCES/"
cp "$REPO_ROOT/data/VERSION.json" "$RESOURCES/"
cp -a "$REPO_ROOT/data/sounds" "$RESOURCES/sounds"
cp -a "$REPO_ROOT/data/fonts" "$RESOURCES/fonts"
mkdir -p "$RESOURCES/marketing"
cp "$REPO_ROOT/marketing/inapp-title.png" "$RESOURCES/marketing/"
cp "$BUILD_DIR/AppIcon.icns" "$RESOURCES/AppIcon.icns"

# Write Info.plist
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>PushNav</string>
    <key>CFBundleDisplayName</key>
    <string>PushNav</string>
    <key>CFBundleIdentifier</key>
    <string>com.pushnav.evf</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>evf</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSCameraUsageDescription</key>
    <string>PushNav uses the camera to capture telescope finder images for plate solving.</string>
</dict>
</plist>
PLIST

echo "==> $APP_NAME.app assembled at $APP_DIR"

# -------------------------------------------------------------------------
# Phase 4: Create .dmg
# -------------------------------------------------------------------------
DMG_PATH="$BUILD_DIR/$APP_NAME.dmg"
echo "==> Creating $DMG_PATH"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$APP_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

echo "==> Build complete!"
echo "    App:  $APP_DIR"
echo "    DMG:  $DMG_PATH"
