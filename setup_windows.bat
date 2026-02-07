@echo off
title DAA Hybrid Installer (Manual Mode)
color 0b
cd /d "%~dp0"

echo ===================================================
echo   DAA HYBRID INSTALLER (MANUAL MODE)
echo ===================================================
echo.

:: 1. CHECK THAT YOU'VE INSTALLED THE RIGHT THINGS
echo [1/5] Checking programs...

where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Python not found!
    echo You must install Python manually from python.org
    echo DON'T FORGET TO CHECK "ADD TO PATH" DURING INSTALLATION!
    pause
    exit /b
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Node.js not found!
    echo You must install Node.js manually from nodejs.org
    pause
    exit /b
)

echo [OK] Python and Node.js found.

:: 2. INSTALL FRONTEND
echo.
echo [2/5] Installing Frontend...
call npm install

:: 3. FIX BACKEND
echo.
echo [3/5] Installing Backend...

if not exist "backend" mkdir backend
cd backend

:: Create requirements.txt
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

:: Create venv
if not exist "venv" (
    echo Creating venv...
    python -m venv venv
)

:: Install packages
echo Installing Python packages (this may take a while)...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. COPY FILES
echo.
echo [4/5] Checking files...
if not exist "app" (
    echo.
    echo [!] Folder 'app' missing in backend.
    echo     Drag and drop your old "DAA_Server" folder here and press ENTER:
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
echo   DONE!
echo   Run 'start_windows.bat' to start.
echo ===================================================
