import numpy as np
import sys
import os

# Mock Config
class Config:
    DEFAULT_CRS = "EPSG:32638"
    WGS84_CRS = "EPSG:4326"

# Add current dir to sys.path
sys.path.append(os.getcwd())

from gaussian_model import GaussianPlumeModel
import pandas as pd

# Mock Data
roads = [None] # Not needed for concentration call
weather = pd.DataFrame({'WS': [0], 'WD': [0], 'TEMP_C': [20]})

model = GaussianPlumeModel(roads, weather)

print(f"Testing wind_speed=0 stability...")
try:
    # x, y, z, source_x, source_y, wind_speed, wind_dir, emission_rate, stability_class
    conc = model.calculate_concentration(100, 0, 0, 0, 0, 0.0, 270, 1000, 'D')
    print(f"SUCCESS: Concentration calculated: {conc}")
except Exception as e:
    print(f"FAILED: {e}")
