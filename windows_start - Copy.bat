@echo off
title DAA - Systemstart
color 0a
cd /d "%~dp0"

echo ===========================================
echo   DAA HYBRID - AUTO START OCH SETUP
echo ===========================================

:: ------------------------------------------------
:: 1. STÄDNING (Döda gamla processer)
:: ------------------------------------------------
echo [SYS] Rensar portar och gamla processer...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM electron.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

:: Döda specifikt processer på port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ------------------------------------------------
:: 2. BACKEND SETUP (Python & Bibliotek)
:: ------------------------------------------------
echo [SYS] Kontrollerar Backend...
cd backend

:: Skapa venv om det saknas
if not exist venv (
    echo [SETUP] Skapar virtuell Python-miljo...
    python -m venv venv
)

:: Aktivera venv
call venv\Scripts\activate

:: Installera/Uppdatera nödvändiga bibliotek
echo [SETUP] Uppdaterar bibliotek...
python -m pip install --upgrade pip >nul 2>&1
pip install mem0ai google-genai >nul 2>&1
pip install --upgrade uvicorn python-socketio websockets >nul 2>&1

:: Installera resten från requirements om de saknas
if exist requirements.txt (
    pip install -r requirements.txt >nul 2>&1
) else (
    REM Fallback om filen saknas
    echo [SETUP] Varning: requirements.txt saknas, installerar standardpaket...
    pip install fastapi "uvicorn[standard]" python-socketio requests google-generativeai openai anthropic mem0ai google-genai
)

:: Gå tillbaka till roten
cd ..

:: ------------------------------------------------
:: 3. FRONTEND SETUP (Node.js)
:: ------------------------------------------------
if not exist node_modules (
    echo [SETUP] Installerar Frontend-paket...
    call npm install
)

:: ------------------------------------------------
:: 4. STARTA APPLIKATIONEN
:: ------------------------------------------------
echo.
echo [SYS] Allt redo. Startar DAA...
echo.

:: Sätt miljövariabler för Python
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

:: Starta via NPM
call npm run dev

pause