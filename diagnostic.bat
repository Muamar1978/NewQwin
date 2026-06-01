@echo off
setlocal
title GPAI - Diagnostics Tool

echo ======================================================
echo      Air Quality Dispersion Model - Diagnostics
echo ======================================================
echo.
echo This tool will check your system for common issues.
echo A report will be saved to "diagnostic_report.txt".
echo.

set REPORT=diagnostic_report.txt
echo GPAI Diagnostic Report > %REPORT%
echo Generated on: %date% %time% >> %REPORT%
echo -------------------------------------- >> %REPORT%

echo [1/5] Checking Python...
python --version >> %REPORT% 2>&1
if %errorlevel% neq 0 (
    echo Python: NOT FOUND >> %REPORT%
    echo [!] Python is not installed or not in PATH.
) else (
    echo Python: FOUND >> %REPORT%
)

echo [2/5] Checking Folders...
if exist .venv (echo .venv: EXISTS >> %REPORT%) else (echo .venv: MISSING >> %REPORT%)
if exist requirements.txt (echo requirements.txt: EXISTS >> %REPORT%) else (echo requirements.txt: MISSING >> %REPORT%)

echo [3/5] Checking Dependencies...
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo --- Installed Packages --- >> %REPORT%
    pip list >> %REPORT%
) else (
    echo [!] Virtual environment not activated. >> %REPORT%
)

echo [4/5] Checking Data Files...
for %%f in (road1.shp road2.shp ERA5_P0INTS.csv Hotspots_AllPollutants_GIS.csv) do (
    if exist %%f (echo %%f: OK >> %REPORT%) else (echo %%f: MISSING >> %REPORT%)
)

echo [5/5] Finalizing...
echo. >> %REPORT%
echo --- End of Report --- >> %REPORT%

echo.
echo ======================================================
echo DIAGNOSTICS COMPLETE!
echo ======================================================
echo Please check the file "diagnostic_report.txt" for details.
echo.
pause
