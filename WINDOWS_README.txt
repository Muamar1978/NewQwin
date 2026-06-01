# Air Quality Dispersion Model - Windows Setup Guide

## For Beginner Users

### Option 1: Run with Python (Recommended)

1. **Install Python 3.8+**
   - Go to https://www.python.org/downloads/
   - Download Python 3.12 (or latest version)
   - **IMPORTANT**: Check "Add Python to PATH" during installation

2. **Install Required Libraries**
   - Double-click `install_dependencies.bat`
   - Wait for all packages to install (may take 5-10 minutes)

3. **Run the Application**
   - Double-click `run_app.bat`
   - Wait for "Running on http://localhost:5000" message
   - Open your browser and go to: **http://localhost:5000**

---

### Option 2: Build Executable (Advanced)

1. **Install Python 3.8+** (if not already installed)

2. **Build the .exe**
   - Double-click `build_windows.bat`
   - Wait for build to complete (may take 15-30 minutes)
   - Find your executable in `dist\AirQualityModel\`

3. **Run the .exe**
   - Go to `dist\AirQualityModel\`
   - Double-click `AirQualityModel.exe`
   - Open browser to http://localhost:5000

---

## Troubleshooting

### "Python not found" error
- Reinstall Python and check "Add Python to PATH"
- Or manually add Python to PATH:
  - Search "Environment Variables" in Start menu
  - Edit PATH and add: `C:\Users\YourName\AppData\Local\Programs\Python\Python312`

### "Module not found" error
- Run `install_dependencies.bat` again
- Make sure you have internet connection

### Application is slow on first run
- Normal for first time - TensorFlow is loading
- Subsequent runs will be faster

### Browser shows "This site can't be reached"
- Wait 10-20 seconds after starting
- Make sure no other program uses port 5000
- Try http://127.0.0.1:5000 instead

---

## Data Format Requirements

### Road Data (Shapefile)
- Files needed: `.shp`, `.shx`, `.dbf`, `.prj` (all in same folder)
- Coordinate system: EPSG:4326 (lat/lon) or UTM

### Weather Data (CSV)
Required columns:
- `TEMP_C` - Temperature (Celsius)
- `WS` - Wind Speed (m/s)
- `WD` - Wind Direction (degrees)

Optional columns:
- `MONTH` - Month (1-12)
- `DAY` - Day (1-31)
- `HOUR` - Hour (0-23)

### Pollution Data (CSV)
Required columns:
- `timestamp` - Date/time (e.g., "2024-01-15 14:00:00")
- `concentration` - Pollution level

### Study Area (Shapefile)
- Polygon shapefile of your area of interest

---

## Quick Start Guide

1. Open application in browser
2. Go to **Upload** tab
3. Upload your road shapefile (Road 1, Road 2, etc.)
4. Upload weather CSV
5. (Optional) Upload study area and pollution data
6. Go to **Simulation** tab
7. Click **Run Simulation**
8. View results on the map!

For forecasts, go to **Forecast** tab and train the model first.
