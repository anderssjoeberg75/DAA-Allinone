@echo off
title DAA Hybrid Launcher
color 0a
cd /d "%~dp0"

echo ===========================================
echo   STARTING DAA HYBRID SYSTEM
echo ===========================================

:: 1. ADVANCED PORT CLEANUP (Port 8000)
echo [SYS] Looking for processes blocking port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo [SYS] Found zombie process PID %%a - Killing it now...
    taskkill /f /pid %%a >nul 2>&1
)

:: Extra cleanup by name (for safety)
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM electron.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

:: Wait a bit so Windows has time to free the port
timeout /t 2 /nobreak >nul

:: 2. SETTINGS
set PYTHONIOENCODING=utf-8

:: 3. START THE APP
echo [SYS] Starting application...
call npm run dev

pause