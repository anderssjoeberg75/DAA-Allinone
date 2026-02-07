@echo off
title DAA - Systemstart
color 0a
cd /d "%~dp0"

echo ===========================================
echo   DAA HYBRID - AUTO START OCH SETUP
echo ===========================================

:: ------------------------------------------------
:: 0. UPDATE FROM GITHUB
:: ------------------------------------------------
echo [SYS] Checking for updates...

:: Check if git exists
git --version >nul 2>&1
if %errorlevel% neq 0 goto NO_GIT

:: Git exists, try to update
echo [GIT] Fetching latest files from GitHub...
git pull
if %errorlevel% neq 0 goto GIT_FAIL

echo [GIT] Update complete.
goto GIT_DONE

:NO_GIT
echo [WARNING] Git not found. Skipping update.
goto GIT_DONE

:GIT_FAIL
color 0E
echo.
echo [WARNING] Could not update (possibly no internet or conflict).
echo Starting anyway with current version...
echo.
color 0a
goto GIT_DONE

:GIT_DONE
echo.

:: ------------------------------------------------
:: 1. CLEANUP (Kill old processes)
:: ------------------------------------------------
echo [SYS] Clearing ports and old processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM electron.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

:: Kill processes specifically on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ------------------------------------------------
:: 2. BACKEND SETUP (Python & Libraries)
:: ------------------------------------------------
echo [SYS] Checking Backend...
cd backend

:: Create venv if missing
if not exist venv (
    echo [SETUP] Creating Python virtual environment...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate

:: Install/Update necessary libraries
echo [SETUP] Updating libraries...
python -m pip install --upgrade pip >nul 2>&1
pip install mem0ai google-genai >nul 2>&1
pip install --upgrade uvicorn python-socketio websockets >nul 2>&1

:: Install the rest from requirements if missing
if exist requirements.txt (
    pip install -r requirements.txt >nul 2>&1
) else (
    REM Fallback if file is missing
    echo [SETUP] Warning: requirements.txt missing, installing default packages...
    pip install fastapi "uvicorn[standard]" python-socketio requests google-generativeai openai anthropic mem0ai google-genai
)

:: Return to root
cd ..

:: ------------------------------------------------
:: 3. FRONTEND SETUP (Node.js)
:: ------------------------------------------------
if not exist node_modules (
    echo [SETUP] Installing Frontend packages...
    call npm install
)

:: ------------------------------------------------
:: 4. START APPLICATION
:: ------------------------------------------------
echo.
echo [SYS] All ready. Starting DAA...
echo.

:: Set environment variables for Python
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

:: Start via NPM
call npm run dev

pause