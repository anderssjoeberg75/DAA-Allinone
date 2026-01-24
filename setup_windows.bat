@echo off
title DAA - Setup och Update
color 0B

echo ===================================================
echo      DAA INSTALLATION OCH UPPDATERING
echo ===================================================
echo.

:: 1. Kontrollera Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [FEL] Python hittades inte!
    echo Installera Python 3.10 eller nyare och kryssa i "Add to PATH".
    pause
    exit /b
)

echo [1/3] Konfigurerar Backend Python...
cd backend

:: Skapa venv om det saknas
if not exist venv (
    echo    - Skapar virtuell miljo venv...
    python -m venv venv
)

:: Aktivera venv
call venv\Scripts\activate

:: Uppdatera pip och installera ALLA krav
echo    - Installerar och uppdaterar bibliotek...
python -m pip install --upgrade pip

:: HÄR ÄR TILLÄGGEN FÖR KODANALYSEN (Anthropic, OpenAI, Google)
pip install fastapi "uvicorn[standard]" python-socketio requests python-multipart google-generativeai openai anthropic

if %errorlevel% neq 0 (
    color 0C
    echo [FEL] Kunde inte installera Python-bibliotek.
    pause
    exit /b
)

echo.
echo [2/3] Konfigurerar Frontend React...
cd ../frontend

:: Kolla om Node.js finns
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [VARNING] Node.js hittades inte. Frontend kanske inte kan byggas.
    echo Detta paverkar dock inte Backend eller Python.
) else (
    if not exist node_modules (
        echo    - Installerar Node-paket...
        call npm install
    ) else (
        echo    - Node_modules finns redan - hoppar over.
    )
)

cd ..
echo.
echo ===================================================
echo [KLART] Installationen ar fardig!
echo.
echo Du kan nu starta systemet med 'start_windows.bat'.
echo ===================================================
pause