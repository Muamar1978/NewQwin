# Air Quality Dispersion Model

A Flask-based web application for Gaussian air pollution dispersion modeling for any city or area worldwide.

---

## Quick Start (All Platforms)

### Windows
Double-click `setup.bat` and follow the instructions, then open **http://localhost:5000**

### Linux/macOS
```bash
chmod +x setup.sh
./setup.sh
```

Then open **http://localhost:5000**

---

## Detailed Windows Installation (Beginner Guide)

### Step 1: Download Python

1. Open your browser and go to: **https://www.python.org/downloads/**
2. Click the **Download Python** button (version 3.11 or newer)
3. Wait for the file to download

### Step 2: Install Python

1. Find the downloaded file (usually in Downloads folder)
2. Right-click and select **Run as administrator**
3. **IMPORTANT**: Check the box that says **"Add Python to PATH"**
   - If you don't see this, the installation may not work!
4. Click **Install Now**
5. Wait for installation to complete (2-5 minutes)
6. Click **Close**

### Step 3: Verify Python Installation

1. Open Command Prompt:
   - Press `Win + R`
   - Type `cmd` and press Enter
2. Type this command and press Enter:
   ```
   python --version
   ```
3. You should see something like `Python 3.11.x` - that's success!

### Step 4: Install the App

1. Download this project (or copy the folder to your computer)
2. Open the folder where you saved the project
3. Double-click **setup.bat**
4. A black window will appear - wait for installation to complete
5. When it says "Installation complete!", the app will start automatically

### Step 5: Open the App

1. The app runs in the Command Prompt window - **keep it open**
2. Open your browser (Chrome, Edge, Firefox, etc.)
3. Type in the address bar: **http://localhost:5000**
4. Press Enter - the app should appear!

---

## How to Use the App

1. **View Map**: The main screen shows a map of your study area
2. **Select Roads**: Use the controls to select which roads to analyze
3. **Choose Pollutant**: Select pollutant type (NOx, CO, PM10, etc.)
4. **Set Traffic**: Enter traffic count
5. **Run Simulation**: Click "Run Simulation" to calculate pollution dispersion
6. **Export**: Download results as Excel or Shapefile

---

## Troubleshooting (Windows)

### "Python not found" error
- Reinstall Python and make sure to check "Add to PATH"
- Or open Command Prompt and type: `where python`

### "pip is not recognized" error
- Open Command Prompt as Administrator
- Type: `python -m pip install --upgrade pip`

### "Port 5000 is already in use"
- Another program is using port 5000
- Open Task Manager and look for Python processes
- Right-click and end those tasks
- Or change the port in app.py line 459: `app.run(..., port=5001)`

### "Module not found" errors
- Reinstall packages:
  ```
  pip uninstall -y flask geopandas pandas numpy pyproj shapely scipy scikit-image openpyxl
  pip install flask geopandas pandas numpy pyproj shapely scipy scikit-image openpyxl
  ```

### App won't open in browser
- Make sure the Command Prompt window is still running
- Check that you're using http://localhost:5000 (not https://)
- Try a different browser

---

## Requirements

- Python 3.8+ (Windows, Linux, macOS)
- All dependencies listed in `requirements.txt`

---

## Features

- GIS viewer with Leaflet maps
- Road network visualization
- Weather data from ERA5
- Gaussian plume dispersion modeling
- Simulation with customizable parameters
- Export results to Excel and Shapefile

---

## Data Files

Ensure these files are in the project folder:
- `road1.shp` - `road4.shp` (road network)
- `ERA5_P0INTS.csv` (weather data)
- `al_mansour_studyarea.shp` (study area)
- `pollution_results.csv` (optional)

---

## Stopping the App

When you're done:
1. Go to the Command Prompt window
2. Press `Ctrl + C`
3. Close the window

To run again later, double-click `setup.bat` or run `python app.py`
