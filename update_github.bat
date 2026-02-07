@echo off
title DAA - Skicka till GitHub
color 0B

echo ===================================================
echo      UPPDATERA GITHUB REPO
echo ===================================================
echo.

:: 1. Kontrollera att Git finns
git --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [FEL] Git ar inte installerat eller ligger inte i PATH.
    echo Ladda ner och installera Git for Windows forst.
    pause
    exit /b
)

:: 2. Visa status
echo Hanger status...
git status -s
echo.

:: 3. Fråga efter kommentar
set /p commit_msg="Skriv vad du har andrat (t.ex. fixat vadret): "

:: Om man bara trycker enter, sätt en standardtext
if "%commit_msg%"=="" set commit_msg="Uppdatering av DAA filer"

echo.
echo [1/3] Staging files...
git add .

echo [2/3] Committing...
git commit -m "%commit_msg%"

echo [3/3] Pushing to GitHub...
git push

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [FEL] Det gick inte att ladda upp till GitHub.
    echo Las felmeddelandet ovan. (Kanske behover du logga in?)
) else (
    color 0A
    echo.
    echo [KLART] Filerna ar uppladdade!
)

echo.
pause