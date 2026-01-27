@echo off
title DAA Hybrid Installer (Manual Mode)
color 0b
cd /d "%~dp0"

echo ===================================================
echo   DAA HYBRID INSTALLER (MANUAL MODE)
echo ===================================================
echo.

:: 1. KONTROLLERA ATT DU INSTALLERAT RÄTT SAKER
echo [1/5] Kontrollerar program...

where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0c
    echo [FEL] Python hittades inte!
    echo Du maste installera Python manuellt fran python.org
    echo GLOM INTE ATT KRYSSA I "ADD TO PATH" VID INSTALLATIONEN!
    pause
    exit /b
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    color 0c
    echo [FEL] Node.js hittades inte!
    echo Du maste installera Node.js manuellt fran nodejs.org
    pause
    exit /b
)

echo [OK] Python och Node.js hittades.

:: 2. INSTALLERA FRONTEND
echo.
echo [2/5] Installerar Frontend...
call npm install

:: 3. FIXA BACKEND
echo.
echo [3/5] Installerar Backend...

if not exist "backend" mkdir backend
cd backend

:: Skapa requirements.txt
if not exist "requirements.txt" (
    (
        echo fastapi
        echo uvicorn[standard]
        echo python-socketio
        echo google-generativeai
        echo openai
        echo anthropic
        echo pydantic
        echo requests
        echo Pillow
        echo pyautogui
        echo opencv-python
        echo paho-mqtt
        echo beautifulsoup4
        echo python-dotenv
        echo aiohttp
        echo garminconnect
        echo httpx
    ) > requirements.txt
)

:: Skapa venv
if not exist "venv" (
    echo Skapar venv...
    python -m venv venv
)

:: Installera paket
echo Installerar Python-paket (detta kan ta en stund)...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. KOPIERA FILER
echo.
echo [4/5] Kontrollerar filer...
if not exist "app" (
    echo.
    echo [!] Mappen 'app' saknas i backend.
    echo     Dra och slapp din gamla mapp "DAA_Server" har och tryck ENTER:
    set /p SERVER_PATH=^> 
)
if defined SERVER_PATH (
    set SERVER_PATH=%SERVER_PATH:"=%
    xcopy "%SERVER_PATH%\app" "app" /E /I /Y
    xcopy "%SERVER_PATH%\config" "config" /E /I /Y
)

cd ..
color 0a
echo.
echo ===================================================
echo   KLART!
echo   Kors 'start_windows.bat' for att starta.
echo ===================================================
