@echo off
REM Copyright (C) 2026 Arun Venkataswamy
REM
REM This file is part of PushNav.
REM
REM PushNav is free software: you can redistribute it and/or modify it
REM under the terms of the GNU General Public License as published by
REM the Free Software Foundation, either version 3 of the License, or
REM (at your option) any later version.
REM
REM PushNav is distributed in the hope that it will be useful, but
REM WITHOUT ANY WARRANTY; without even the implied warranty of
REM MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
REM General Public License for more details.
REM
REM You should have received a copy of the GNU General Public License
REM along with PushNav. If not, see <https://www.gnu.org/licenses/>.

REM Launch EVF in development mode on Windows.
REM Assumes camera server has been built via camera\windows\build.bat.
cd /d "%~dp0.."

uv sync || exit /b 1

uv run python scripts/build_catalogs.py --needs-rebuild
if not errorlevel 1 (
    echo ==^> Rebuilding catalog JSONs
    uv run python scripts/build_catalogs.py || exit /b 1
)

REM evf.main auto-detects Vite on :5173 and otherwise loads the prebuilt
REM bundle from :8765 -- rebuild on every dev launch so source edits are
REM reflected. Skipped when Vite is serving HMR on :5173 because the
REM bundle isn't read in that path.
netstat -an | findstr ":5173" | findstr "LISTENING" >nul
if errorlevel 1 (
    REM npm writes node_modules\.package-lock.json after install -- if
    REM the repo's package-lock.json is newer (e.g. after a `git pull`
    REM that added deps), reinstall before building. Also installs when
    REM node_modules or its .package-lock.json is missing (fresh checkout).
    set "NEEDS_INSTALL="
    if not exist "web\node_modules" set "NEEDS_INSTALL=1"
    if not exist "web\node_modules\.package-lock.json" set "NEEDS_INSTALL=1"
    if not defined NEEDS_INSTALL powershell -NoProfile -Command "if ((Get-Item 'web\package-lock.json').LastWriteTime -gt (Get-Item 'web\node_modules\.package-lock.json').LastWriteTime) { exit 1 } else { exit 0 }"
    if errorlevel 1 set "NEEDS_INSTALL=1"
    if defined NEEDS_INSTALL (
        echo ==^> Installing web\ npm dependencies
        pushd web
        call npm install || ( popd & exit /b 1 )
        popd
    )
    echo ==^> Rebuilding React bundle ^(no Vite on :5173^)
    pushd web
    call npm run build || ( popd & exit /b 1 )
    popd
)

uv run python -m evf.main
