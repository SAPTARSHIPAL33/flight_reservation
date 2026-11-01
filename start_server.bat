@echo off
title AeroBook Flight Reservation Server Launcher
cd /d "%~dp0"

echo ===================================================
echo   Starting AeroBook Backend Server on Port 8000
echo ===================================================
echo.

:: Launch the FastAPI backend in its own persistent console window
start "AeroBook Backend" cmd /k ""%~dp0venv\Scripts\python.exe" "%~dp0run.py""

:: Wait 3 seconds for uvicorn to initialize
echo Waiting for server to initialize...
timeout /t 3 /nobreak >nul

:: Open web application in default browser
echo Opening AeroBook in your browser...
start "" "http://127.0.0.1:8000/"

echo.
echo ===================================================
echo   AeroBook Server is running!
echo   Web App URL: http://127.0.0.1:8000/
echo ===================================================
echo.
echo You can keep this window open or close it.
echo (The "AeroBook Backend" window must remain open while using the app).
pause
