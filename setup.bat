@echo off
setlocal
title GPAI - First Time Setup

echo ======================================================
echo   Air Quality Dispersion Model - Setup Wizard
echo ======================================================
echo.

:: 1. Check for Python installation
echo [1/4] Checking for Python...
set PYTHON_CMD=python
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    set PYTHON_CMD=py
    %PYTHON_CMD% --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Python not found on your computer!
        echo.
        echo Steps to fix:
        echo 1. Go to: https://www.python.org/downloads/
        echo 2. Click "Download Python 3.12" ^(or newer^)
        echo 3. IMPORTANT: When installing, check the box: 
        echo    "Add Python to PATH"
        echo 4. After installation, restart this setup.
        echo.
        pause
        exit /b 1
    )
)
echo Found: 
%PYTHON_CMD% --version

:: 2. Create Virtual Environment
echo.
echo [2/4] Preparing project environment...
if not exist .venv (
    echo Creating isolated environment ^(.venv^)...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Failed to create virtual environment. 
        echo Ensure you have permissions to write to this folder.
        pause
        exit /b 1
    )
) else (
    echo Environment already exists. Skipping creation.
)

:: 3. Install Dependencies
echo.
echo [3/4] Installing necessary components...
echo (This may take 5-10 minutes depending on your internet speed)
echo.

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Installation failed!
    echo Possible causes:
    echo - No internet connection
    echo - Interrupted download
    echo.
    echo Please check your connection and try running setup.bat again.
    pause
    exit /b 1
)

:: 4. Finalizing
echo.
echo [4/4] Finalizing setup...
if not exist output mkdir output
if not exist uploads mkdir uploads

echo.
echo ======================================================
echo        SETUP COMPLETED SUCCESSFULLY!
echo ======================================================
echo.
echo You can now run the application by double-clicking:
echo --^> run.bat
echo.
pause
