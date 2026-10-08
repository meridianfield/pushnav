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

# Build the pushnav-headless .deb (Raspberry Pi, arm64, always headless).
#
# Usage:
#   scripts/build_headless_deb.sh          # build in a Debian bookworm container (Docker)
#   scripts/build_headless_deb.sh --host   # build directly on this arm64 machine
#
# The container is the release path: camera_server is compiled against
# bookworm's glibc (2.36) so the one .deb runs on Pi OS bookworm and
# trixie. On an x86 PC Docker runs the arm64 image under QEMU (slow; needs
# qemu-user-static + binfmt-support). --host is for quick iteration on a
# Pi and needs gcc, libjpeg-dev, Node 20.19+, curl and uv.
#
# Output: build/pushnav-headless_<version>_arm64.deb
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# node:22-bookworm = Debian bookworm + Node 22 (Vite 8 needs Node 20.19+)
# + gcc and libjpeg-dev from buildpack-deps.
BUILD_IMAGE="${PUSHNAV_BUILD_IMAGE:-node:22-bookworm}"
UV_VERSION="0.12.23"

MODE="${1:-docker}"
case "$MODE" in
    docker)
        echo "==> Building in $BUILD_IMAGE (linux/arm64)"
        exec docker run --rm --platform linux/arm64 \
            -v "$REPO_ROOT:/src" -w /src \
            -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
            -e PUSHNAV_DEB_REVISION \
            "$BUILD_IMAGE" bash scripts/build_headless_deb.sh --in-container
        ;;
    --host|--in-container) ;;
    *) echo "usage: $0 [--host]" >&2; exit 2 ;;
esac

if [ "$(uname -m)" != "aarch64" ]; then
    echo "ERROR: pushnav-headless is arm64-only; this machine is $(uname -m)." >&2
    echo "       Run without --host to build in an arm64 container." >&2
    exit 1
fi

umask 022
WORK="$REPO_ROOT/build/headless"
STAGE="$WORK/root"
APP="$STAGE/usr/lib/pushnav-headless"
PKG_DIR="$REPO_ROOT/packaging/headless"

rm -rf "$WORK"
mkdir -p "$APP/data" "$APP/marketing"
cd "$REPO_ROOT"

# -------------------------------------------------------------------------
# Phase 0: tools
# -------------------------------------------------------------------------
if [ "$MODE" = "--in-container" ] && ! dpkg -s libjpeg-dev >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq --no-install-recommends libjpeg-dev
fi
UV="$(command -v uv || true)"
if [ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
fi
if [ -z "$UV" ]; then
    echo "==> Installing uv $UV_VERSION"
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" \
        | env UV_INSTALL_DIR="$WORK/uv-bin" INSTALLER_NO_MODIFY_PATH=1 sh -s -- --quiet
    UV="$WORK/uv-bin/uv"
fi
export UV_LINK_MODE=copy

# -------------------------------------------------------------------------
# Phase 1: camera server (same flags as camera/linux/Makefile)
# -------------------------------------------------------------------------
echo "==> Building camera_server"
gcc -Wall -Wextra -O2 -o "$APP/camera_server" camera/linux/camera_server.c -ljpeg
strip "$APP/camera_server"

# -------------------------------------------------------------------------
# Phase 2: React UI, built from a clean copy so the repo's node_modules and
# dist/ are left alone.
# -------------------------------------------------------------------------
echo "==> Building web UI"
mkdir -p "$WORK/web"
tar -C web --exclude=./node_modules --exclude=./dist -cf - . | tar -C "$WORK/web" -xf -
(cd "$WORK/web" && npm ci --no-audit --no-fund --loglevel=error && npm run build)
cp -a "$WORK/web/dist" "$APP/data/web_dist"

# -------------------------------------------------------------------------
# Phase 3: bundled Python (python-build-standalone, relocatable) with the
# runtime deps — no `desktop` group, so no pywebview / PyQt6.
# -------------------------------------------------------------------------
PY_VERSION="$(cat .python-version)"
echo "==> Bundling Python $PY_VERSION"
UV_PYTHON_INSTALL_DIR="$WORK/pythons" "$UV" python install --quiet "$PY_VERSION"
PY_SRC="$(dirname "$(dirname "$(UV_PYTHON_INSTALL_DIR="$WORK/pythons" \
    "$UV" python find --managed-python "$PY_VERSION")")")"
cp -a "$PY_SRC" "$APP/python"
PY="$APP/python/bin/python3"
PY_LIB="$APP/python/lib/python${PY_VERSION%.*}"
rm -f "$PY_LIB/EXTERNALLY-MANAGED"

"$UV" export --quiet --frozen --no-dev --no-group desktop --no-emit-project \
    --project "$REPO_ROOT" -o "$WORK/requirements.txt"
"$UV" pip install --quiet --python "$PY" -r "$WORK/requirements.txt"
"$UV" pip install --quiet --python "$PY" --no-deps "$REPO_ROOT"

# Drop what a headless service never imports: stdlib tests / IDLE / Tk,
# pip, and gaia-catalog (a tetra3rs dependency only needed to regenerate
# data/tetra3rs_gaia.bin; SolverDatabase.load_from_file doesn't use it).
SITE="$PY_LIB/site-packages"
rm -rf "$PY_LIB/test" "$PY_LIB/idlelib" "$PY_LIB/tkinter" "$PY_LIB/turtledemo" \
    "$PY_LIB"/lib-dynload/_tkinter* "$APP/python/lib"/libtcl* "$APP/python/lib"/libtk* \
    "$APP/python/lib"/tcl[0-9]* "$APP/python/lib"/tk[0-9]* "$APP/python/lib"/itcl* \
    "$APP/python/lib"/thread[0-9]* "$APP/python/share" \
    "$SITE"/pip "$SITE"/pip-* "$SITE"/gaia_catalog "$SITE"/gaia_catalog-* \
    "$APP/python/bin"/pip*
find "$APP/python" -name __pycache__ -type d -prune -exec rm -rf {} +
# Precompile bytecode: /usr/lib is read-only to the service user, so
# Python could never cache it at runtime. unchecked-hash ignores mtimes.
"$PY" -m compileall -q -j0 --invalidation-mode unchecked-hash "$APP/python/lib" >/dev/null

# -------------------------------------------------------------------------
# Phase 4: data (same set as the Linux release, see build_linux.sh)
# -------------------------------------------------------------------------
echo "==> Copying data"
cp data/tetra3rs_gaia.bin data/VERSION.json "$APP/data/"
cp -a data/sounds "$APP/data/sounds"
cp -a tests/samples "$APP/data/samples"
cp marketing/inapp-title.png "$APP/marketing/"

# -------------------------------------------------------------------------
# Phase 5: launcher, systemd unit, docs, maintainer scripts
# -------------------------------------------------------------------------
install -D -m 755 "$PKG_DIR/pushnav-headless" "$STAGE/usr/bin/pushnav-headless"
install -D -m 644 "$PKG_DIR/pushnav-headless.service" \
    "$STAGE/usr/lib/systemd/system/pushnav-headless.service"
install -d "$STAGE/usr/share/doc/pushnav-headless"
cat > "$STAGE/usr/share/doc/pushnav-headless/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: PushNav
Source: https://github.com/meridianfield/pushnav

Files: *
Copyright: 2026 Arun Venkataswamy
License: GPL-3+
 On Debian systems the full text of the GNU General Public License
 version 3 is in /usr/share/common-licenses/GPL-3.
 .
 The bundled Python runtime and Python packages under
 /usr/lib/pushnav-headless/python keep their own licenses (see each
 package's *.dist-info directory). The OpenNGC and HYG catalogs bundled
 in the web UI are CC-BY-SA 4.0.
EOF

RAW_VERSION="$("$PY" -c "import json; print(json.load(open('data/VERSION.json'))['app_version'])")"
# 0.3.0-beta -> 0.3.0~beta-1 ('~' sorts before the final 0.3.0)
DEB_VERSION="${RAW_VERSION/-/\~}-${PUSHNAV_DEB_REVISION:-1}"

chmod -R u+rwX,go+rX,go-w "$STAGE"
install -d -m 755 "$STAGE/DEBIAN"
for s in postinst prerm postrm; do
    install -m 755 "$PKG_DIR/debian/$s" "$STAGE/DEBIAN/$s"
done
INSTALLED_SIZE="$(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)"
sed -e "s/@VERSION@/$DEB_VERSION/" -e "s/@INSTALLED_SIZE@/$INSTALLED_SIZE/" \
    "$PKG_DIR/debian/control.in" > "$STAGE/DEBIAN/control"

# -------------------------------------------------------------------------
# Phase 6: .deb
# -------------------------------------------------------------------------
DEB="$REPO_ROOT/build/pushnav-headless_${DEB_VERSION}_arm64.deb"
echo "==> Packing $(basename "$DEB")"
rm -f "$DEB"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB" >/dev/null

if [ "$MODE" = "--in-container" ] && [ -n "${HOST_UID:-}" ]; then
    chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" "$REPO_ROOT/build"
fi

echo "==> Done: $DEB"
echo "    package $(du -h "$DEB" | cut -f1), installed $((INSTALLED_SIZE / 1024)) MB"
