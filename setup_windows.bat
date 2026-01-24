@echo off
title DAA Setup
color 0A

echo ===================================================
echo      DAA DIGITAL ADVANCED ASSISTANT - SETUP
echo ===================================================
echo.

:: --- STEG 1: PYTHON ---
echo [1/4] Kontrollerar Python...
python --version >nul 2>&1
if %errorlevel% neq 0 goto NO_PYTHON
echo       - Python OK.

:: --- STEG 2: BACKEND ---
echo.
echo [2/4] Konfigurerar Backend...
cd backend

if exist venv goto VENV_EXISTS
echo       - Skapar venv...
python -m venv venv
:VENV_EXISTS

echo       - Aktiverar venv och installerar paket...
call venv\Scripts\activate

python -m pip install --upgrade pip >nul 2>&1
pip install fastapi "uvicorn[standard]" python-socketio requests python-dotenv python-weather google-generativeai openai anthropic garminconnect stravalib pydantic httpx

if %errorlevel% neq 0 goto PIP_ERROR

deactivate
cd ..
echo       - Backend klar.

:: --- STEG 3: FRONTEND ---
echo.
echo [3/4] Konfigurerar Frontend...
node --version >nul 2>&1
if %errorlevel% neq 0 goto NO_NODE

echo       - Installerar NPM-paket...
call npm install
call npm install lucide-react
goto SETUP_FOLDERS

:NO_NODE
echo [VARNING] Node.js saknas. Hoppar over frontend-installation.

:: --- STEG 4: MAPPSTRUKTUR ---
:SETUP_FOLDERS
echo.
echo [4/4] Skapar mappar...
if not exist logs mkdir logs
if not exist backend\config\garmin_tokens mkdir backend\config\garmin_tokens

echo.
echo ===================================================
echo    INSTALLATION KLAR!
echo ===================================================
echo.
echo Du kan nu kora start_windows.bat
pause
exit /b

:: --- FELHANTERING ---

:NO_PYTHON
color 0C
echo.
echo [FEL] Python hittades inte.
echo Installera Python 3.10+ och kryssa i "Add to PATH".
pause
exit /b

:PIP_ERROR
color 0C
echo.
echo [FEL] Kunde inte installera Python-paket.
echo Kontrollera din internetanslutning.
pause
exit /b