@echo off
title CampusNet NOC Server
echo ======================================================================
echo    Starting CampusNet: Adaptive Network Optimization Operations Center
echo ======================================================================
echo.
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.10+ and check 'Add python.exe to PATH'.
    pause
    exit /b 1
)

echo Checking dependencies...
python -m pip install -r requirements.txt --quiet

echo.
echo Launching CampusNet server on http://127.0.0.1:5000 ...
echo (Keep this window open while using CampusNet. Press Ctrl+C to stop).
echo.
start http://127.0.0.1:5000
python app.py
pause
