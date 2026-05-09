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

set -euo pipefail
cd "$(dirname "$0")/.."

# pywebview on Linux uses PyGObject (`gi`), which ships only as a distro
# package (apt install python3-gi gir1.2-webkit2-4.1) and is not on PyPI.
# The venv must inherit system site-packages so it can import `gi`.
if [ ! -d .venv ]; then
    echo "==> Creating .venv with --system-site-packages (pywebview needs system PyGObject)"
    uv venv --system-site-packages
elif ! grep -q '^include-system-site-packages = true' .venv/pyvenv.cfg 2>/dev/null; then
    echo "ERROR: .venv exists but was created without --system-site-packages."
    echo "       pywebview cannot import the system 'gi' module from this venv."
    echo "       Fix: rm -rf .venv && uv venv --system-site-packages && uv sync"
    exit 1
fi

uv sync

# evf.main auto-detects Vite on :5173 and otherwise loads the prebuilt
# bundle from :8765 — make sure web/dist exists when Vite isn't running.
if ! (exec 3<>/dev/tcp/localhost/5173) 2>/dev/null; then
    if [ ! -f web/dist/index.html ]; then
        if [ ! -d web/node_modules ]; then
            echo "==> Installing web/ npm dependencies"
            (cd web && npm install)
        fi
        echo "==> No Vite on :5173 and no web/dist — building React bundle"
        (cd web && npm run build)
    fi
fi

uv run python -m evf.main
