@echo off
title MASTERINGAUDS — Audio Mastering Suite
echo.
echo   ==========================================
echo     MASTERINGAUDS — Audio Mastering Suite
echo     http://localhost:5000
echo   ==========================================
echo.

cd /d "%~dp0"

if not exist ".venv" (
    echo   Creating virtual environment...
    python -m venv .venv
    echo.
)

echo   Activating virtual environment...
call .venv\Scripts\activate.bat

echo   Installing dependencies...
pip install -q -r requirements.txt
echo.

echo   Starting server...
echo.
python app.py

pause
