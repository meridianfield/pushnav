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
# Phase 1b: Build React UI
# -------------------------------------------------------------------------
echo "==> Building React UI"
(cd "$REPO_ROOT/web" && npm ci && npm run build)
if [ ! -f "$REPO_ROOT/web/dist/index.html" ]; then
    echo "ERROR: React build did not produce web/dist/index.html"
    exit 1
fi

# -------------------------------------------------------------------------
# Phase 1c: Generate app icon (.icns) — must precede Nuitka so the
#           bundle gets it baked in via --macos-app-icon.
# -------------------------------------------------------------------------
echo "==> Generating app icon"
LOGO="$REPO_ROOT/marketing/logo.png"
ICONSET="$BUILD_DIR/AppIcon.iconset"
ICON_PATH="$BUILD_DIR/AppIcon.icns"
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

iconutil --convert icns "$ICONSET" --output "$ICON_PATH"
rm -rf "$ICONSET"
echo "    Icon: $ICON_PATH"

# -------------------------------------------------------------------------
# Phase 2: Build Python app with Nuitka (--mode=app)
# -------------------------------------------------------------------------
# Nuitka 4.x's options-nanny refuses to compile any code that imports
# Foundation (pulled in by pywebview's Cocoa backend) unless --mode=app
# is used. --mode=app implies --standalone and creates the .app bundle
# with a default Info.plist; we pass app metadata via the --macos-app-*
# flags instead of writing the plist by hand.
# -------------------------------------------------------------------------
echo "==> Building Python app with Nuitka (--mode=app)"
uv run python -m nuitka \
    --mode=app \
    --static-libpython=no \
    --output-dir="$BUILD_DIR" \
    --output-filename=evf \
    --macos-app-name="$APP_NAME" \
    --macos-app-version="$APP_VERSION" \
    --macos-app-icon="$ICON_PATH" \
    --macos-signed-app-name="com.pushnav.evf" \
    --macos-app-protected-resource="NSCameraUsageDescription:PushNav uses the camera to capture telescope finder images for plate solving." \
    --include-package=numpy \
    --include-package=scipy \
    --include-package=PIL \
    --include-package=playsound3 \
    --include-package=tetra3 \
    --include-package=erfa \
    --nofollow-import-to=pytest \
    --nofollow-import-to=setuptools \
    `# Exclude stdlib C extensions we genuinely don't need. _ssl / _hashlib /` \
    `# _blake2 are NOT in this list — pywebview's webview.http imports ssl,` \
    `# and aiohttp uses hashlib, so excluding them crashes the binary on launch.` \
    --nofollow-import-to=_curses \
    --nofollow-import-to=_curses_panel \
    --nofollow-import-to=_dbm \
    --nofollow-import-to=_gdbm \
    --nofollow-import-to=_tkinter \
    --nofollow-import-to=readline \
    --assume-yes-for-downloads \
    "$REPO_ROOT/python/evf/main.py"

# Nuitka --mode=app names the output directory after the source filename
# (main.py → main.app); --macos-app-name only sets CFBundleName / display
# name. Rename so the rest of the script can refer to a stable APP_DIR.
NUITKA_APP="$BUILD_DIR/main.app"
if [ ! -d "$NUITKA_APP" ]; then
    echo "ERROR: Nuitka did not produce $NUITKA_APP"
    exit 1
fi
mv "$NUITKA_APP" "$APP_DIR"

# -------------------------------------------------------------------------
# Phase 3: Drop in resources Nuitka doesn't know about (camera binary,
# star database, sounds, web bundle, sample images, branding image).
# Nuitka has already populated Contents/MacOS/ with the Python runtime
# and Contents/Resources/ with the icon.
# -------------------------------------------------------------------------
echo "==> Adding camera + data resources to $APP_NAME.app"

cp "$CAMERA_BIN" "$MACOS/camera_server"
chmod +x "$MACOS/camera_server"

cp "$REPO_ROOT/data/hip8_database.npz" "$RESOURCES/"
cp "$REPO_ROOT/data/VERSION.json" "$RESOURCES/"
cp -a "$REPO_ROOT/data/sounds"      "$RESOURCES/sounds"
cp -a "$REPO_ROOT/web/dist"         "$RESOURCES/web_dist"
cp -a "$REPO_ROOT/tests/samples"    "$RESOURCES/samples"
mkdir -p "$RESOURCES/marketing"
cp "$REPO_ROOT/marketing/inapp-title.png" "$RESOURCES/marketing/"

echo "==> $APP_NAME.app assembled at $APP_DIR"

# -------------------------------------------------------------------------
# Phase 4: Create styled .dmg via dmgbuild
# -------------------------------------------------------------------------
# dmgbuild (Python, in the repo's dev dep group) writes the volume's
# .DS_Store directly via ds-store + mac-alias — bypassing the
# AppleScript / Finder Automation path that broke for create-dmg on
# Sequoia. Settings live in scripts/dmgbuild_settings.py; the .app and
# background paths come in via env vars.
# -------------------------------------------------------------------------
DMG_PATH="$BUILD_DIR/$APP_NAME.dmg"
echo "==> Creating styled $DMG_PATH"
rm -f "$DMG_PATH"

PUSHNAV_APP_PATH="$APP_DIR" \
PUSHNAV_BG_PATH="$REPO_ROOT/marketing/dmg-background.png" \
uv run dmgbuild \
    -s "$SCRIPT_DIR/dmgbuild_settings.py" \
    "$APP_NAME" \
    "$DMG_PATH"

echo "==> Build complete!"
echo "    App:  $APP_DIR"
echo "    DMG:  $DMG_PATH"
