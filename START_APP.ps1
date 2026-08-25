# Insurance Risk Adjustment Tool - PowerShell Startup Script
# Right-click and "Run with PowerShell" or execute: powershell -ExecutionPolicy Bypass -File START_APP.ps1

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "Insurance Risk Adjustment Tool" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

Write-Host "Starting Flask application..." -ForegroundColor Yellow

# Change to script directory
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Activate virtual environment
& ".\venv\Scripts\Activate.ps1"

# Run Flask app
python app.py

Write-Host "`nServer stopped." -ForegroundColor Yellow
pause
