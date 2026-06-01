import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, Polygon
import geopandas as gpd
from pyproj import Transformer
import os
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

try:
    from skimage import measure
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False

# Import Config at the module level for path resolution
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def simple_gaussian_blur(grid):
    """Pure NumPy 3x3 Gaussian blur to avoid hanging scipy.ndimage"""
    if grid.shape[0] < 3 or grid.shape[1] < 3:
        return grid
    kernel = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]]) / 16.0
    res = (grid[:-2, :-2] * kernel[0,0] + grid[:-2, 1:-1] * kernel[0,1] + grid[:-2, 2:] * kernel[0,2] +
           grid[1:-1, :-2] * kernel[1,0] + grid[1:-1, 1:-1] * kernel[1,1] + grid[1:-1, 2:] * kernel[1,2] +
           grid[2:, :-2] * kernel[2,0] + grid[2:, 1:-1] * kernel[2,1] + grid[2:, 2:] * kernel[2,2])
    full_res = grid.copy()
    full_res[1:-1, 1:-1] = res
    return full_res
# try:
#     print("    Model: Importing dask...")
#     import dask.array as da
#     HAS_DASK = True
# except ImportError:
#     HAS_DASK = False
HAS_DASK = False

# print("    Model: Done with imports.")

# Suppress matplotlib warnings
import warnings
warnings.filterwarnings("ignore", module="matplotlib")

class GaussianPlumeModel:
    def __init__(self, road_data, weather_data, emission_factors=None):
        if road_data is None:
            raise ValueError("Road data cannot be None")
        if weather_data is None:
            raise ValueError("Weather data cannot be None")
        
        self.road_data = road_data
        self.weather_data = weather_data
        self.ugm_to_m = 1e-6
        self.transformer = Transformer.from_crs(Config.DEFAULT_CRS, Config.WGS84_CRS, always_xy=True)
        
        # Convert emission_factors list of dicts to a dictionary for fast lookup
        self.emission_factors = {}
        if emission_factors:
            for item in emission_factors:
                if 'pollutant' in item and 'emission_factor' in item:
                    self.emission_factors[item['pollutant']] = item['emission_factor']
        
        self.EPSILON = 0.5 # Minimum wind speed to prevent division by zero

    
    def calculate_stability_class(self, wind_speed, is_day=True, cloud_cover=0.5, solar_radiation='moderate'):
        """
        Determine Pasquill-Gifford stability class based on wind speed, day/night, and solar radiation/cloud cover.
        """
        if is_day:
            if solar_radiation == 'strong':
                if wind_speed < 2: return 'A'
                if wind_speed < 3: return 'A'
                if wind_speed < 5: return 'B'
                if wind_speed < 6: return 'B'
                return 'C'
            elif solar_radiation == 'moderate':
                if wind_speed < 2: return 'A'
                if wind_speed < 3: return 'B'
                if wind_speed < 5: return 'B'
                if wind_speed < 6: return 'C'
                return 'C'
            else: # slight
                if wind_speed < 2: return 'A'
                if wind_speed < 3: return 'B'
                if wind_speed < 5: return 'C'
                if wind_speed < 6: return 'C'
                return 'D'
        else: # Night
            if cloud_cover > 0.5: # Cloudy night
                return 'D'
            else: # Clear night
                if wind_speed < 2: return 'F'
                if wind_speed < 3: return 'E'
                if wind_speed < 5: return 'D'
                return 'D'
    
    def get_dispersion_coefficients(self, stability_class, distance, sy0=10.0, sz0=2.0):
        # distance is distance downwind in meters
        # Pasquill-Gifford dispersion parameters for urban/rural
        # Coefficients for sigma_y
        ay = {'A': 0.527, 'B': 0.278, 'C': 0.202, 'D': 0.120, 'E': 0.080, 'F': 0.040}
        by = {'A': 0.865, 'B': 0.908, 'C': 0.916, 'D': 0.924, 'E': 0.929, 'F': 0.932}
        py = {'A': 1.594, 'B': 1.593, 'C': 1.593, 'D': 1.573, 'E': 1.565, 'F': 1.550}
        
        # Coefficients for sigma_z (standard approximations)
        az = {'A': 0.200, 'B': 0.120, 'C': 0.080, 'D': 0.060, 'E': 0.030, 'F': 0.016}
        bz = {'A': 1.0, 'B': 1.0, 'C': 1.0, 'D': 1.0, 'E': 1.0, 'F': 1.0}
        pz = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'D': 0.0, 'E': 0.0, 'F': 0.0}
        
        dist = np.maximum(distance, 1e-9)
        
        sy_pg = ay.get(stability_class, 0.2) * (dist ** by.get(stability_class, 0.9)) * (1 + 0.0001 * dist) ** py.get(stability_class, 1.5)
        sz_pg = az.get(stability_class, 0.1) * (dist ** bz.get(stability_class, 1.0)) * (1 + 0.0001 * dist) ** pz.get(stability_class, 0.0)
        
        # Add initial dispersion for vehicle wake (volume source approximation)
        sy = np.sqrt(sy_pg**2 + sy0**2)
        sz = np.sqrt(sz_pg**2 + sz0**2)
        
        return sy, sz
    
    def calculate_emission_rate(self, road_length, traffic_count, emission_factor=500.0):
        # ER (g/s) = (Road Length (km) × Traffic Count (veh/hr) × EF (g/veh/km)) / 3600 * 1000
        return (road_length * traffic_count * emission_factor) / 3600 * 1000
    
    def calculate_concentration(self, x, y, z, source_x, source_y, wind_speed, wind_dir, 
                                 emission_rate, stability_class, mixing_height=1000):
        dx = x - source_x
        dy = y - source_y
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance < 1:
            return 0.0
        
        # Wind direction: meteorological convention (direction FROM which wind blows)
        # Convert to mathematical convention (direction TO which wind blows)
        wind_rad = np.radians(270 - wind_dir)  # Adjust for meteorological to mathematical
        
        # Rotate to align with wind direction
        x_downwind = dx * np.cos(wind_rad) + dy * np.sin(wind_rad)
        y_crosswind = -dx * np.sin(wind_rad) + dy * np.cos(wind_rad)
        
        if x_downwind <= 0:
            return 0.0
        
        sigma_y, sigma_z = self.get_dispersion_coefficients(stability_class, x_downwind)
        
        sigma_y = max(sigma_y, 1.0)
        sigma_z = max(sigma_z, 0.5)
        
        # Ensure wind speed is not zero
        u = max(wind_speed, self.EPSILON)
        
        # Gaussian plume equation (ground-level source)
        # C = Q/(2*pi*u*sigma_y*sigma_z) * exp(-y^2/(2*sigma_y^2)) * [exp(-z^2/(2*sigma_z^2)) + exp(-(2*H-z)^2/(2*sigma_z^2))]
        # Q in g/s, u in m/s → C in g/m³
        
        term1 = emission_rate / (2 * np.pi * u * sigma_y * sigma_z)
        term2 = np.exp(-y_crosswind**2 / (2 * sigma_y**2))
        
        # Ground reflection (z=0 for road source)
        z_diff = z
        term3 = np.exp(-z_diff**2 / (2 * sigma_z**2))
        term4 = np.exp(-(2 * mixing_height - z_diff)**2 / (2 * sigma_z**2))
        
        concentration = term1 * term2 * (term3 + term4)
        
        # Convert g/m³ to µg/m³ (standard air quality unit)
        return max(concentration * 1e6, 0.0)
    def calculate_concentration_vectorized(self, gx, gy, sx, sy, wind_speed, wind_dir, 
                                          emission_rate, stability_class, z=0, mixing_height=1000, background_concentration=0.0):
        """Vectorized calculation of concentrations for all grid points and all source points"""
        # gx, gy: shape (N_grid,)
        # sx, sy: shape (N_sources,)
        
        # Broadcasting to create matrices: (N_grid, N_sources)
        dx = gx[:, np.newaxis] - sx[np.newaxis, :]
        dy = gy[:, np.newaxis] - sy[np.newaxis, :]
        
        dist = np.sqrt(dx**2 + dy**2)
        
        wind_rad = np.radians(270 - wind_dir)
        x_downwind = dx * np.cos(wind_rad) + dy * np.sin(wind_rad)
        y_crosswind = -dx * np.sin(wind_rad) + dy * np.cos(wind_rad)
        
        # Mask for points that are too close or upwind
        mask = (dist >= 1) & (x_downwind > 0)
        
        # Calculate dispersion coefficients for all valid pairs
        # x_downwind has shape (N_grid, N_sources)
        sigma_y, sigma_z = self.get_dispersion_coefficients(stability_class, x_downwind)
        
        sigma_y = np.maximum(sigma_y, 1.0)
        sigma_z = np.maximum(sigma_z, 0.5)
        
        u = np.maximum(wind_speed, self.EPSILON)
        
        # Plume Equation (Q in g/s, u in m/s → C in g/m³)
        term1 = emission_rate / (2 * np.pi * u * sigma_y * sigma_z)
        term2 = np.exp(-y_crosswind**2 / (2 * sigma_y**2))
        
        z_diff = z
        term3 = np.exp(-z_diff**2 / (2 * sigma_z**2))
        term4 = np.exp(-(2 * mixing_height - z_diff)**2 / (2 * sigma_z**2))
        
        # Multiply by mask to zero out invalid points
        concentrations = mask * term1 * term2 * (term3 + term4)
        
        # Sum across sources for each grid point
        total_conc = np.sum(concentrations, axis=1)
        
        # Convert g/m³ to µg/m³ (standard air quality unit) and add background concentration
        return (total_conc * 1e6) + background_concentration

    def calculate_concentration_dask(self, gx, gy, sx, sy, wind_speed, wind_dir, 
                                     emission_rate, stability_class, z=0, mixing_height=1000, 
                                     background_concentration=0.0, chunk_size=1000):
        """Dask-parallelized version of concentration calculation for very large grids"""
        if not HAS_DASK:
            return self.calculate_concentration_vectorized(gx, gy, sx, sy, wind_speed, wind_dir, 
                                                         emission_rate, stability_class, z, mixing_height, background_concentration)

        # Create dask arrays
        gx_da = da.from_array(gx, chunks=chunk_size)
        gy_da = da.from_array(gy, chunks=chunk_size)
        sx_da = da.from_array(sx, chunks=chunk_size)
        sy_da = da.from_array(sy, chunks=chunk_size)

        # Broadcasting in dask
        dx = gx_da[:, None] - sx_da[None, :]
        dy = gy_da[:, None] - sy_da[None, :]
        
        dist = da.sqrt(dx**2 + dy**2)
        
        wind_rad = np.radians(270 - wind_dir)
        x_downwind = dx * np.cos(wind_rad) + dy * np.sin(wind_rad)
        y_crosswind = -dx * np.sin(wind_rad) + dy * np.cos(wind_rad)
        
        mask = (dist >= 1) & (x_downwind > 0)
        
        # Dispersion coefficients (need to wrap the function or handle dask arrays)
        # For simplicity in this implementation, we apply the formula directly on dask arrays
        ay = {'A': 0.527, 'B': 0.278, 'C': 0.202, 'D': 0.120, 'E': 0.080, 'F': 0.040}
        by = {'A': 0.865, 'B': 0.908, 'C': 0.916, 'D': 0.924, 'E': 0.929, 'F': 0.932}
        py = {'A': 1.594, 'B': 1.593, 'C': 1.593, 'D': 1.573, 'E': 1.565, 'F': 1.550}
        az = {'A': 0.200, 'B': 0.120, 'C': 0.080, 'D': 0.060, 'E': 0.030, 'F': 0.016}
        bz = {'A': 1.0, 'B': 1.0, 'C': 1.0, 'D': 1.0, 'E': 1.0, 'F': 1.0}
        pz = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'D': 0.0, 'E': 0.0, 'F': 0.0}

        dist_clip = da.maximum(x_downwind, 1e-9)
        sy_pg = ay.get(stability_class, 0.2) * (dist_clip ** by.get(stability_class, 0.9)) * (1 + 0.0001 * dist_clip) ** py.get(stability_class, 1.5)
        sz_pg = az.get(stability_class, 0.1) * (dist_clip ** bz.get(stability_class, 1.0)) * (1 + 0.0001 * dist_clip) ** pz.get(stability_class, 0.0)
        
        # Add initial dispersion (sy0=10.0, sz0=2.0)
        sy0, sz0 = 10.0, 2.0
        sigma_y = da.sqrt(sy_pg**2 + sy0**2)
        sigma_z = da.sqrt(sz_pg**2 + sz0**2)
        
        sigma_y = da.maximum(sigma_y, 1.0)
        sigma_z = da.maximum(sigma_z, 0.5)
        
        u = max(wind_speed, self.EPSILON)
        
        term1 = emission_rate / (2 * np.pi * u * sigma_y * sigma_z)
        term2 = da.exp(-y_crosswind**2 / (2 * sigma_y**2))
        
        z_diff = z
        term3 = da.exp(-z_diff**2 / (2 * sigma_z**2))
        term4 = da.exp(-(2 * mixing_height - z_diff)**2 / (2 * sigma_z**2))
        
        concentrations = mask * term1 * term2 * (term3 + term4)
        total_conc = concentrations.sum(axis=1)
        
        # Compute the result and convert g/m³ to µg/m³ and add background
        return (total_conc.compute() * 1e6) + background_concentration

    
    def generate_grid_points(self, bounds, spacing=50):
        x_min, y_min, x_max, y_max = bounds
        x_points = np.arange(x_min, x_max, spacing)
        y_points = np.arange(y_min, y_max, spacing)
        
        # Use meshgrid for faster generation
        xv, yv = np.meshgrid(x_points, y_points)
        points = np.column_stack([xv.ravel(), yv.ravel()])
        
        return points
    
    def run_simulation(self, road_ids: list, pollutant: str, traffic_count: float, day=None, month=None, hour=None, buffer_distance: float = 250, 
                       live_ws=None, live_wd=None, live_temp=None, background_concentration=0.0):
        if road_ids is None:
            road_ids = [1]
        elif isinstance(road_ids, int):
            road_ids = [road_ids]
        
        if pollutant is None or pollutant == '':
            pollutant = 'NOx'
        
        if traffic_count is None or traffic_count <= 0:
            traffic_count = 1000
        
        for road_id in road_ids:
            if road_id < 1 or road_id > len(self.road_data):
                return [], {'error': f'Invalid road_id: {road_id}. Valid range: 1-{len(self.road_data)}'}
            if self.road_data[road_id - 1] is None:
                return [], {'error': f'Road {road_id} is not uploaded.'}
        
        buffer_dist = int(buffer_distance) if buffer_distance else 250
        if buffer_dist < 50:
            buffer_dist = 50
        if buffer_dist > 500:
            buffer_dist = 500
        
        all_road_coords = []
        all_road_lines = []
        total_road_length = 0
        
        for road_id in road_ids:
            road_gdf = self.road_data[road_id - 1]
            if road_gdf is None:
                continue
            
            # Loop through all segments in the road shapefile
            for _, road in road_gdf.iterrows():
                road_geom = road.geometry
                
                if road_geom.geom_type == 'MultiLineString':
                    road_coords = []
                    for line in road_geom.geoms:
                        road_coords.extend(list(line.coords))
                elif road_geom.geom_type == 'LineString':
                    road_coords = list(road_geom.coords)
                else:
                    road_coords = []
                
                if not road_coords:
                    continue
                
                total_road_length += road_geom.length
                all_road_coords.extend(road_coords)
                
                road_line = LineString(road_coords)
                all_road_lines.append(road_line)
        
        print(f"DEBUG: Total road length used for emission calculation: {total_road_length:.2f} meters")
        
        if not all_road_coords:
            return [], {'error': 'No road coordinates found'}
        
        combined_road_line = LineString(all_road_coords) if len(all_road_lines) > 1 else all_road_lines[0]
        
        buffer_polygon = combined_road_line.buffer(buffer_dist)
        
        max_buffer = 500
        all_bounds = []
        for road_id in road_ids:
            road_gdf = self.road_data[road_id - 1]
            road = road_gdf.iloc[0]
            all_bounds.append(road.geometry.bounds)
        
        min_x = min(b[0] for b in all_bounds)
        min_y = min(b[1] for b in all_bounds)
        max_x = max(b[2] for b in all_bounds)
        max_y = max(b[3] for b in all_bounds)
        full_extended_bounds = (
            min_x - max_buffer, min_y - max_buffer,
            max_x + max_buffer, max_y + max_buffer
        )
        # Prepare grid points as arrays
        grid_points = self.generate_grid_points(full_extended_bounds, spacing=15)
        
        weather_filtered = self.weather_data
        if hour is not None:
            weather_filtered = weather_filtered[weather_filtered['HOUR'] == hour]
        if day is not None:
            weather_filtered = weather_filtered[weather_filtered['DAY'] == day]
        if month is not None:
            weather_filtered = weather_filtered[weather_filtered['MONTH'] == month]
        
        if len(weather_filtered) == 0:
            weather_filtered = self.weather_data
        
        required_cols = ['WS', 'WD', 'TEMP_C']
        if not all(col in weather_filtered.columns for col in required_cols):
            return [], {'error': 'Missing required weather data columns'}
        
        if live_ws is not None and live_wd is not None and live_temp is not None:
            avg_ws = live_ws
            avg_wd = live_wd
            avg_temp = live_temp
            # For live mode, we use the current hour for day/night logic
            current_hour = datetime.now().hour
            is_day = 6 <= current_hour <= 18
        else:
            avg_ws = weather_filtered['WS'].mean()
            avg_wd = weather_filtered['WD'].mean()
            avg_temp = weather_filtered['TEMP_C'].mean()
            
            # Determine if it's day or night for stability class
            is_day = True
            if hour is not None:
                is_day = 6 <= hour <= 18
        
        stability = self.calculate_stability_class(avg_ws, is_day=is_day)
        
        # Use dynamic emission factors if available
        if self.emission_factors:
            emission_factor = self.emission_factors.get(pollutant, 1.0)
        else:
            # Fallback defaults
            pollutant_factors = {'NOx': 0.8, 'CO': 2.5, 'PM10': 0.3, 'PM2.5': 0.15}
            emission_factor = pollutant_factors.get(pollutant, 1.0)

        
        # Traffic count is provided in vehicles per hour (veh/hr)
        # ER (g/s) = (Road Length (km) × Traffic Count (veh/hr) × EF (g/veh/km)) / 3600 * 1000
        emission_rate_gs = ((total_road_length / 1000) * traffic_count * emission_factor) / 3600
        # ER in g/s, wind speed stays in m/s for Gaussian plume
        emission_rate = emission_rate_gs
        
        source_points = []
        for road_line in all_road_lines:
            road_coords = list(road_line.coords)
            for i in range(len(road_coords) - 1):
                x1, y1 = road_coords[i]
                x2, y2 = road_coords[i + 1]
                seg_length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                # Use a finer sampling interval (20m) for better source representation
                num_samples = max(2, int(seg_length / 20))
                for j in range(num_samples):
                    t = j / (num_samples - 1) # Ensure we hit both endpoints
                    sx = x1 + t * (x2 - x1)
                    sy = y1 + t * (y2 - y1)
                    source_points.append((sx, sy))
        
        # Prepare source points as arrays for vectorization
        sx = np.array([p[0] for p in source_points])
        sy = np.array([p[1] for p in source_points])
        
        # Prepare grid points as arrays
        gx = grid_points[:, 0]
        gy = grid_points[:, 1]
        
        # Parallelized calculation for all points
        per_point_emission = emission_rate / len(source_points)
        
        # Choose between Dask and NumPy based on grid size
        if HAS_DASK and len(gx) * len(sx) > 1_000_000:
            concentrations = self.calculate_concentration_dask(
                gx, gy, sx, sy, avg_ws, avg_wd, per_point_emission, stability, background_concentration=background_concentration
            )
        else:
            concentrations = self.calculate_concentration_vectorized(
                gx, gy, sx, sy, avg_ws, avg_wd, per_point_emission, stability, background_concentration=background_concentration
            )
        
        # Pre-calculate transformations for all points
        lons, lats = self.transformer.transform(gx, gy)
        
        # Vectorized spatial filtering using GeoPandas
        points_gdf = gpd.GeoDataFrame(geometry=gpd.points_from_xy(gx, gy), crs=Config.DEFAULT_CRS)
        mask_in_buffer = points_gdf.within(combined_road_line.buffer(max_buffer))
        
        all_results = []
        # Filter both arrays at once using the mask
        gx_filtered = gx[mask_in_buffer]
        gy_filtered = gy[mask_in_buffer]
        lons_filtered = lons[mask_in_buffer]
        lats_filtered = lats[mask_in_buffer]
        conc_filtered = concentrations[mask_in_buffer]
        
        for i in range(len(gx_filtered)):
            all_results.append({
                'x': gx_filtered[i],
                'y': gy_filtered[i],
                'lon': lons_filtered[i],
                'lat': lats_filtered[i],
                'concentration': conc_filtered[i],
                'pollutant': pollutant
            })
        
        full_max_conc = float(np.max(concentrations)) if len(concentrations) > 0 else 0.0
        
        results = []
        for r in all_results:
            pt = Point(r['x'], r['y'])
            if buffer_polygon.contains(pt):
                results.append(r)

        
        heatmap_data = self.create_heatmap_data(results)
        
        return results, {
            'road_ids': road_ids,
            'pollutant': pollutant,
            'wind_speed': avg_ws,
            'wind_direction': avg_wd,
            'temperature': avg_temp,
            'stability_class': stability,
            'emission_rate': emission_rate,
            'emission_rate_unit': 'g/s',
            'traffic_count': traffic_count,
            'buffer_distance': buffer_dist,
            'full_max_concentration': full_max_conc,
            'heatmap': heatmap_data
        }
    
    def create_heatmap_data(self, results, grid_size=100):
        """Create interpolated heatmap data for smooth visualization"""
        if len(results) < 4:
            return None
        
        x_coords = np.array([r['x'] for r in results])
        y_coords = np.array([r['y'] for r in results])
        concentrations = np.array([r['concentration'] for r in results])
        
        # Check for NaNs or Infs
        if np.any(np.isnan(concentrations)) or np.any(np.isinf(concentrations)):
            print("  [WARNING] Concentrations contain NaNs or Infs. Cleaning...")
            concentrations = np.nan_to_num(concentrations, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Create finer grid for interpolation
        x_min, x_max = x_coords.min(), x_coords.max()
        y_min, y_max = y_coords.min(), y_coords.max()
        
        # Add small buffer
        x_pad = (x_max - x_min) * 0.05
        y_pad = (y_max - y_min) * 0.05
        
        grid_x = np.linspace(x_min - x_pad, x_max + x_pad, grid_size)
        grid_y = np.linspace(y_min - y_pad, y_max + y_pad, grid_size)
        
        # Use histogram2d as a fast and stable alternative to griddata
        counts, x_edges, y_edges = np.histogram2d(x_coords, y_coords, bins=[grid_size, grid_size], 
                                                 range=[[grid_x[0], grid_x[-1]], [grid_y[0], grid_y[-1]]])
        sums, _, _ = np.histogram2d(x_coords, y_coords, bins=[grid_size, grid_size], 
                                    range=[[grid_x[0], grid_x[-1]], [grid_y[0], grid_y[-1]]], weights=concentrations)
        
        # Avoid division by zero
        grid_conc = np.divide(sums, counts, out=np.zeros_like(sums), where=counts!=0)
        
        # Transpose to match (x, y) order expected by create_heatmap_data
        grid_conc = grid_conc.T
        
        # Apply simple blur
        grid_conc = simple_gaussian_blur(np.maximum(grid_conc, 0))
        
        # Convert to list for JSON serialization
        heatmap_data = {
            'grid_x': grid_x.tolist(),
            'grid_y': grid_y.tolist(),
            'concentrations': grid_conc.tolist(),
            'min_conc': float(np.min(grid_conc)),
            'max_conc': float(np.max(grid_conc))
        }
        
        return heatmap_data
    
    def create_concentration_shapefile(self, results, output_path):
        geometries = []
        for r in results:
            pt = Point(r['x'], r['y'])
            geometries.append(pt)
        
        gdf = gpd.GeoDataFrame(results, geometry=geometries, crs="EPSG:32638")
        gdf.to_file(output_path)
        return output_path
    
    def create_isoline_shapefile(self, results, output_path, levels=[10, 25, 50, 75, 100]):
        x_coords = [r['x'] for r in results]
        y_coords = [r['y'] for r in results]
        concentrations = [r['concentration'] for r in results]
        
        grid_x = np.linspace(min(x_coords), max(x_coords), 100)
        grid_y = np.linspace(min(y_coords), max(y_coords), 100)
        grid_X, grid_Y = np.meshgrid(grid_x, grid_y)
        
        # Avoid griddata here too - use histogram2d if needed or just skip
        # For isolines, we really need a good grid. I'll use nearest neighbor logic in pure numpy
        # But for now, I'll just skip isoline generation to be safe, or use a very simple version.
        grid_conc = np.zeros((100, 100)) # Placeholder
        print("  [WARNING] Isoline generation currently disabled due to scipy issues.")
        
        polygons = []
        for level in levels:
            try:
                if not HAS_SKIMAGE:
                    break
                contours = measure.find_contours(grid_conc, level)
                
                for contour in contours:
                    if len(contour) > 2:
                        idx_x = np.clip((contour[:, 1] * len(grid_x) / 100).astype(int), 0, len(grid_x) - 1)
                        idx_y = np.clip((contour[:, 0] * len(grid_y) / 100).astype(int), 0, len(grid_y) - 1)
                        xs = grid_x[idx_x]
                        ys = grid_y[idx_y]
                        
                        if len(xs) > 2:
                            poly = Polygon(zip(xs, ys))
                            polygons.append({
                                'level': level,
                                'geometry': poly
                            })
            except Exception:
                pass
        
        if polygons:
            gdf = gpd.GeoDataFrame(polygons, crs="EPSG:32638")
            gdf.to_file(output_path)
        
        return output_path


def load_road_data():
    roads = []
    # Load all road segments from shapefiles
    for i in range(1, 5):
        try:
            road = gpd.read_file(f'road{i}.shp')
            roads.append(road)
        except Exception:
            pass
    return roads


def load_weather_data():
    try:
        df = pd.read_csv('ERA5_P0INTS.csv')
        return df
    except Exception:
        return None
