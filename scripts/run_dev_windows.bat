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

REM evf.main auto-detects Vite on :5173 and otherwise loads the prebuilt
REM bundle from :8765 -- make sure web\dist exists when Vite isn't running.
netstat -an | findstr ":5173" | findstr "LISTENING" >nul
if errorlevel 1 (
    if not exist "web\dist\index.html" (
        if not exist "web\node_modules" (
            echo ==^> Installing web\ npm dependencies
            pushd web
            call npm install || ( popd & exit /b 1 )
            popd
        )
        echo ==^> No Vite on :5173 and no web\dist -- building React bundle
        pushd web
        call npm run build || ( popd & exit /b 1 )
        popd
    )
)

uv run python -m evf.main
