
import time
print("1. Importing flask...")
start = time.time()
from flask import Flask, render_template
print(f"   Done in {time.time() - start:.2f}s")

print("2. Importing flask_cors...")
start = time.time()
from flask_cors import CORS
print(f"   Done in {time.time() - start:.2f}s")

print("3. Importing config...")
start = time.time()
from config import Config
print(f"   Done in {time.time() - start:.2f}s")

print("4. Importing routes.data...")
start = time.time()
from routes.data import data_bp, initialize_default_data
print(f"   Done in {time.time() - start:.2f}s")

print("5. Importing routes.simulation...")
start = time.time()
from routes.simulation import sim_bp
print(f"   Done in {time.time() - start:.2f}s")

print("6. Importing routes.forecast...")
start = time.time()
from routes.forecast import forecast_bp
print(f"   Done in {time.time() - start:.2f}s")

print("7. Importing routes.export...")
start = time.time()
from routes.export import export_bp
print(f"   Done in {time.time() - start:.2f}s")

print("All imports successful!")
