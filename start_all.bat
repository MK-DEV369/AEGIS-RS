@echo off
title AEGIS-RS Unified Control Launcher
color 0B
echo =======================================================================
echo  AEGIS ACTIVE ADAS PLATFORM UNIFIED LAUNCHER
echo =======================================================================
echo.

set WORKSPACE_ROOT=E:\6th SEM Data\Projects\AEGIS-RS_IDP
set BACKEND_DIR=%WORKSPACE_ROOT%\fog-alert-platform\backend
set FRONTEND_DIR=%WORKSPACE_ROOT%\fog-alert-platform\frontend

echo [*] Workspace Root: %WORKSPACE_ROOT%
echo [*] Checking directories and virtual environments...

if not exist "%BACKEND_DIR%" (
    echo [ERROR] Backend directory not found: %BACKEND_DIR%
    goto error
)

if not exist "%FRONTEND_DIR%" (
    echo [ERROR] Frontend directory not found: %FRONTEND_DIR%
    goto error
)

if not exist "%BACKEND_DIR%\venv\Scripts\activate.bat" (
    echo [ERROR] Backend Python virtual environment not found in: %BACKEND_DIR%\venv
    goto error
)

echo.
echo [+] Directories verified successfully.
echo [*] Starting services in separate windows...
echo.

:: 1. Start Django Backend Server
echo [1/3] Launching Django Backend Server...
start "AEGIS ADAS Backend Server" cmd /k "cd /d %BACKEND_DIR% && echo [BACKEND] Starting Django dev server... && venv\Scripts\python manage.py runserver"
timeout /t 2 /nobreak >nul

:: 2. Start React Frontend Dev Server
echo [2/3] Launching React Frontend Dev Server...
start "AEGIS ADAS Frontend Server" cmd /k "cd /d %FRONTEND_DIR% && echo [FRONTEND] Starting Vite dev server... && npm run dev"
timeout /t 2 /nobreak >nul

:: 3. Start ESP32 Serial Relay Daemon
echo [3/3] Launching ESP32 Serial Relay...
start "AEGIS ESP32 Serial Relay" cmd /k "cd /d %BACKEND_DIR% && echo [RELAY] Starting ESP32 Serial Relay Daemon... && venv\Scripts\python -u scripts\esp32_relay.py"

echo.
echo =======================================================================
echo  SUCCESS: All services started in separate console windows!
echo  Check the opened command prompts to monitor logs and telemetry.
echo =======================================================================
echo.
pause
exit

:error
echo.
echo [!] Launcher failed due to missing files/directories.
pause
exit /b 1
