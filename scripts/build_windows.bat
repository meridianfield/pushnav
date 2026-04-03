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

REM Build PushNav Windows release (zip)
REM Usage: scripts\build_windows.bat
REM
REM Prerequisites:
REM   - Visual Studio Build Tools (cl.exe on PATH via vcvarsall.bat)
REM   - uv, python3, nuitka
REM   - (Optional) libjpeg-turbo for YUYV fallback
REM   - (Optional) Inno Setup 6 for installer: winget install JRSoftware.InnoSetup

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "BUILD_DIR=%REPO_ROOT%\build"
set "APP_NAME=PushNav-windows"
set "APP_DIR=%BUILD_DIR%\%APP_NAME%"

REM Read version from VERSION.json (single source of truth)
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "(Get-Content '%REPO_ROOT%\data\VERSION.json' | ConvertFrom-Json).app_version"`) do set "APP_VERSION=%%V"
echo ==> Version: %APP_VERSION%

echo ==> Cleaning previous build
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"

REM -------------------------------------------------------------------------
REM Phase 1: Build C camera server
REM -------------------------------------------------------------------------
echo ==> Building C camera server
pushd "%REPO_ROOT%\camera\windows"
call build.bat
if errorlevel 1 (
    echo ERROR: Camera server build failed
    popd
    exit /b 1
)
set "CAMERA_BIN=%REPO_ROOT%\camera\windows\camera_server.exe"
if not exist "%CAMERA_BIN%" (
    echo ERROR: camera_server.exe not found
    popd
    exit /b 1
)
popd

REM -------------------------------------------------------------------------
REM Phase 2: Build Python with Nuitka (standalone)
REM -------------------------------------------------------------------------
echo ==> Building Python app with Nuitka (standalone)
uv run python -m nuitka ^
    --standalone ^
    --windows-disable-console ^
    --windows-icon-from-ico="%REPO_ROOT%\marketing\logo.ico" ^
    --output-dir="%BUILD_DIR%" ^
    --output-filename=evf.exe ^
    --include-package=dearpygui ^
    --include-package=numpy ^
    --include-package=scipy ^
    --include-package=PIL ^
    --include-package=playsound3 ^
    --include-package=tetra3 ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=setuptools ^
    --assume-yes-for-downloads ^
    "%REPO_ROOT%\python\evf\main.py"

set "NUITKA_DIST=%BUILD_DIR%\main.dist"
if not exist "%NUITKA_DIST%" (
    echo ERROR: Nuitka dist not found at %NUITKA_DIST%
    exit /b 1
)

REM -------------------------------------------------------------------------
REM Phase 3: Assemble release directory
REM -------------------------------------------------------------------------
echo ==> Assembling %APP_NAME%
mkdir "%APP_DIR%\data" 2>nul
mkdir "%APP_DIR%\marketing" 2>nul

REM Copy Nuitka standalone dist
xcopy /s /e /q /y "%NUITKA_DIST%\*" "%APP_DIR%\"

REM Copy camera server binary
copy /y "%CAMERA_BIN%" "%APP_DIR%\camera_server.exe"

REM Copy data resources
copy /y "%REPO_ROOT%\data\hip8_database.npz" "%APP_DIR%\data\"
copy /y "%REPO_ROOT%\data\VERSION.json" "%APP_DIR%\data\"
xcopy /s /e /q /y "%REPO_ROOT%\data\sounds" "%APP_DIR%\data\sounds\"
xcopy /s /e /q /y "%REPO_ROOT%\data\fonts" "%APP_DIR%\data\fonts\"

REM Copy marketing assets
copy /y "%REPO_ROOT%\marketing\inapp-title.png" "%APP_DIR%\marketing\"
copy /y "%REPO_ROOT%\marketing\logo.ico" "%APP_DIR%\marketing\"

echo ==> Release directory assembled at %APP_DIR%

REM -------------------------------------------------------------------------
REM Phase 4: Create zip
REM -------------------------------------------------------------------------
set "ZIP_NAME=PushNav-windows-x64.zip"
set "ZIP_PATH=%BUILD_DIR%\%ZIP_NAME%"
echo ==> Creating %ZIP_NAME%
powershell -NoProfile -Command "Compress-Archive -Path '%APP_DIR%' -DestinationPath '%ZIP_PATH%' -Force"

REM -------------------------------------------------------------------------
REM Phase 5: Create installer (Inno Setup)
REM -------------------------------------------------------------------------
REM Try common Inno Setup locations (system-wide and per-user winget install)
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "!ISCC!"=="" (
    echo ==> SKIP: Inno Setup not found
    echo     Install with: winget install JRSoftware.InnoSetup
    goto :done
)

echo ==> Creating Windows installer
"!ISCC!" /DAPP_VERSION="%APP_VERSION%" "%REPO_ROOT%\scripts\pushnav.iss"
if errorlevel 1 (
    echo ERROR: Installer build failed
    exit /b 1
)

set "SETUP_PATH=%BUILD_DIR%\PushNav-windows-x64-setup.exe"

:done
echo.
echo ==> Build complete!
echo     Dir:  %APP_DIR%
echo     Zip:  %ZIP_PATH%
if defined SETUP_PATH if exist "%SETUP_PATH%" echo     Setup: %SETUP_PATH%
