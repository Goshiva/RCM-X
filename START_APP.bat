@echo off
REM Insurance Risk Adjustment Tool - Windows Startup Script
REM This script starts the Flask web application

cd /d "%~dp0"

echo.
echo ================================================
echo Insurance Risk Adjustment Tool
echo ================================================
echo.
echo Starting Flask application...
echo.

REM Activate virtual environment and run Flask
call venv\Scripts\activate.bat
python app.py

echo.
echo Server stopped.
pause
