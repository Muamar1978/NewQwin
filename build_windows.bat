@echo off
echo ============================================
echo   Air Quality Dispersion Model - Builder
echo ============================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python found
echo.

echo Installing dependencies...
echo This may take a few minutes...
pip install flask flask-cors geopandas pandas numpy pyproj shapely scipy scikit-image dask[complete] distributed tensorflow pyinstaller --quiet

echo.
echo Building executable...
echo Please wait...
pyinstaller airquality_model.spec --clean

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo Your executable is in: dist\AirQualityModel\
echo.
echo To run the application:
echo   1. Go to dist\AirQualityModel\ folder
echo   2. Double-click AirQualityModel.exe
echo   3. Open your browser and go to http://localhost:5000
echo.
echo NOTE: The first run may take longer as TensorFlow
echo       and other libraries are loading.
echo.
pause
