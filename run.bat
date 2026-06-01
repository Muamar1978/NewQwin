@echo off
setlocal
title GPAI - Launching...

echo ======================================================
echo      Air Quality Dispersion Model - Launcher
echo ======================================================
echo.

:: 1. Check for Virtual Environment
echo [1/3] Checking environment...
if not exist .venv (
    echo.
    echo [ERROR] Virtual environment not found!
    echo.
    echo Please run "setup.bat" first to install everything.
    echo.
    pause
    exit /b 1
)

:: 2. Start checking for server availability in the background or just wait
:: We'll use a slightly longer timeout and then start the browser
echo [2/3] Activating environment...
call .venv\Scripts\activate.bat

:: 3. Start the application
echo [3/3] Starting the local server...
echo.
echo ======================================================
echo   APP IS STARTING! KEEP THIS WINDOW OPEN.
echo   To stop the app, close this window or press Ctrl+C.
echo ======================================================
echo.

:: Launch browser in background after 3 seconds
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000"

:: Run Flask
python app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application stopped unexpectedly.
    echo.
    echo Tip: Try running "diagnostic.bat" to find the problem.
    echo.
    pause
    exit /b 1
)

pause
