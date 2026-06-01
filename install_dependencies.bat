@echo off
echo ============================================
echo   Installing Dependencies
echo   Air Quality Dispersion Model
echo ============================================
echo.

pip install flask flask-cors geopandas pandas numpy pyproj shapely scipy scikit-image dask[complete] distributed tensorflow 2>&1

echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Now you can run the application by:
echo   1. Double-click run_app.bat
echo   2. Open browser to http://localhost:5000
echo.
pause
