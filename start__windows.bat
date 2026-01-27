@echo off
title DAA Hybrid Launcher
color 0a
cd /d "%~dp0"

echo ===========================================
echo   STARTAR DAA HYBRID SYSTEM
echo ===========================================

:: 1. AVANCERAD PORT-RENSNING (Port 8000)
echo [SYS] Letar efter processer som blockerar port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo [SYS] Hittade zombie-process PID %%a - Dodar den nu...
    taskkill /f /pid %%a >nul 2>&1
)

:: Extra stadning av namn (for sakerhets skull)
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM electron.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

:: Vanta lite sa Windows hinner frigora porten
timeout /t 2 /nobreak >nul

:: 2. INSTALLLINGAR
set PYTHONIOENCODING=utf-8

:: 3. STARTA APPEN
echo [SYS] Startar applikationen...
call npm run dev

pause