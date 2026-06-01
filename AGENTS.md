# AGENTS.md - Air Quality Dispersion Model

## Project Overview

This is a Flask-based web application for Gaussian air pollution dispersion modeling for any city or area worldwide. It processes GIS data from shapefiles, runs atmospheric dispersion simulations, and provides a GIS viewer with dashboard.

## Build/Lint/Test Commands

### Running the Application

```bash
# Start the Flask development server
python3 app.py

# The app runs on http://localhost:5000
```

### Running Tests

```bash
# Run a single test (using pytest)
pytest tests/ -v
pytest tests/test_gaussian_model.py::test_gaussian_concentration -v

# Or test specific API endpoint
curl http://localhost:5000/api/roads
curl http://localhost:5000/api/weather
```

### Dependencies

Required packages (install with `--user --break-system-packages`):
- flask
- geopandas
- pandas
- numpy
- pyproj
- shapely
- scipy
- scikit-image
- dask[complete]
- distributed

## Performance Optimization (Dask & Multiprocessing)

The application includes high-performance simulation capabilities:
- **Dask Parallelization**: Automatically used for simulations with >1M source-grid point combinations.
- **Vectorized NumPy**: Used for standard simulations to minimize overhead.
- **Multiprocessing Ready**: Optimized for multi-core scaling.

You can adjust chunk sizes in `gaussian_model.py` to tune performance for your specific hardware.

### Python Backend (app.py, gaussian_model.py)

**Imports**
- Standard library first, then third-party, then local
- Use explicit relative imports for local modules
- Group: stdlib, third-party, local

```python
# Correct
import json
import os
from flask import Flask, jsonify
from gaussian_model import GaussianPlumeModel
import geopandas as gpd

# Avoid
from flask import *
import sys, os
```

**Formatting**
- 4 spaces for indentation (no tabs)
- Line length: 100 characters max
- Use Black for code formatting: `black .`

**Types**
- Use type hints for function signatures
- Prefer explicit typing over dynamic

```python
# Good
def calculate_concentration(x: float, y: float, z: float) -> float:
    ...

# Avoid
def calculate_concentration(x, y, z):
    ...
```

**Naming Conventions**
- Classes: `PascalCase` (e.g., `GaussianPlumeModel`)
- Functions/variables: `snake_case` (e.g., `run_simulation`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `UGM_TO_M = 1e-6`)
- Private functions: prefix with `_` (e.g., `_calculate_stability`)

**Error Handling**
- Use try/except with specific exceptions
- Log errors before re-raising
- Return meaningful error messages via API

```python
# Good
try:
    result = model.run_simulation(road_id, pollutant, traffic)
except ValueError as e:
    return jsonify({'error': str(e)}), 400
except Exception as e:
    logger.error(f"Simulation failed: {e}")
    return jsonify({'error': 'Internal server error'}), 500
```

**API Design**
- RESTful endpoints with proper HTTP methods
- Return JSON with consistent structure
- Use status codes correctly (200, 400, 404, 500)

### Frontend (templates/index.html)

**JavaScript**
- Use ES6+ syntax (const/let, arrow functions, template literals)
- Use async/await for fetch calls
- Prefer const over let

```javascript
// Good
const response = await fetch('/api/roads');
const roads = await response.json();

roads.forEach(road => {
    L.geoJSON(road, { style: { color: '#00d9ff' } }).addTo(map);
});
```

**CSS**
- Use CSS variables for colors
- Mobile-first responsive design
- Use flexbox/grid for layouts
- Follow BEM naming for complex components

**Leaflet Integration**
- Use GeoJSON for vector data
- Layer groups for toggleable layers
- Include proper attribution

### GIS/Geospatial

**Coordinate Systems**
- Internal storage: EPSG:32638 (UTM Zone 38N)
- Frontend display: EPSG:4326 (WGS84)
- Always transform coordinates using pyproj

```python
transformer = Transformer.from_crs("EPSG:32638", "EPSG:4326", always_xy=True)
lon, lat = transformer.transform(x, y)
```

**Shapefiles**
- Use geopandas for reading/writing
- Include .prj files for CRS
- Handle both Point and Polygon geometries

### Gaussian Dispersion Model

**Model Parameters**
- Stability classes: A-F (Pasquill-Gifford)
- Dispersion coefficients based on distance and stability
- Wind speed, direction, temperature from ERA5 data

**Output**
- Concentration grids as GeoJSON
- Shapefile export with proper attributes
- Isoline generation for visualization

## Project Structure

```
demo001/
├── app.py                 # Flask application and API endpoints
├── gaussian_model.py      # Gaussian plume dispersion model
├── templates/
│   └── index.html         # Frontend GIS viewer and dashboard
├── output/                # Generated shapefiles and GeoJSON
├── road1.shp, road2.shp  # Road network data
├── ERA5_P0INTS.csv        # Weather data
├── pollution_results.csv # Existing pollution measurements
└── AGENTS.md            # This file
```

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main application |
| `/api/roads` | GET | Road network GeoJSON |
| `/api/weather` | GET | Weather statistics |
| `/api/simulate` | POST | Run dispersion simulation |
| `/api/shapefile` | POST | Generate shapefile output |
| `/api/pollution-data` | GET | Existing pollution points |
| `/api/study-area` | GET | Study area boundary |

## Common Tasks

### Running a simulation
```javascript
// From frontend - click "Run Simulation" button
// Or via API:
curl -X POST http://localhost:5000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"road_id": 1, "pollutant": "NOx", "traffic_count": 1000}'
```

### Adding a new road
1. Add shapefile to project directory (road3.shp, etc.)
2. The app automatically loads roads numbered 1-4
3. Recycle or restart the Flask server

### Modifying dispersion parameters
Edit `gaussian_model.py`:
- `calculate_stability_class()` - atmospheric stability
- `get_dispersion_coefficients()` - sigma_y, sigma_z
- `calculate_concentration()` - main formula
