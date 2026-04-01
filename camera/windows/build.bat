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

REM Build the Windows DirectShow camera server.
REM Run from a Visual Studio Developer Command Prompt, or after calling vcvarsall.bat.
REM
REM Usage:
REM   build.bat           Build camera_server.exe
REM   build.bat clean     Remove build artifacts
REM
REM For YUYV fallback with libjpeg-turbo, add:
REM   /DHAVE_LIBJPEG /I"path\to\libjpeg\include" and jpeg.lib to the link step.

setlocal

if "%1"=="clean" (
    echo Cleaning build artifacts...
    del /q camera_server.exe 2>nul
    del /q camera_server.obj 2>nul
    echo Done.
    goto :eof
)

echo Building camera_server.exe...
cl.exe /W4 /O2 /Fe:camera_server.exe camera_server.c ^
    ws2_32.lib ole32.lib oleaut32.lib strmiids.lib uuid.lib

if errorlevel 1 (
    echo BUILD FAILED
    exit /b 1
)

echo Build succeeded: camera_server.exe
for %%F in (camera_server.exe) do echo Size: %%~zF bytes
