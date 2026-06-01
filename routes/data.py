from flask import Blueprint, request, jsonify
import os
import shutil
import requests
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
# print("  Data Route: Importing fiona...")
# import fiona
from config import Config
from state import get_session_data, update_session_data, get_transformer, set_session_data
import state # To update transformer globally
import numpy as np
from services.weather_service import fetch_live_weather, fetch_live_pollution
import struct
from shapely.geometry import LineString, Point, Polygon

data_bp = Blueprint('data', __name__)

# fiona.drvsupport.supported_drivers['ESRI Shapefile'] = 'rw'

@data_bp.route('/api/reset', methods=['POST'])
def reset_simulation():
    try:
        # Reset session data using cache
        default_data = {
            'roads': [],
            'weather_data': None,
            'study_area': None,
            'pollution_data': None,
            'historical_pollution': None,
            'forecast_model': None,
            'crs': Config.DEFAULT_CRS,
            'simulation_results': [],
            'emission_factors': None,
            'last_forecast': None,
            'coordinate_data': None,
            'data_scaler': None,
            'pollutant_name': None
        }
        set_session_data(default_data)
        
        if os.path.exists(Config.OUTPUT_DIR):
            for f in os.listdir(Config.OUTPUT_DIR):
                if f.startswith('concentration_') or f.startswith('isoline_') or f.startswith('simulation_'):
                    try:
                        os.remove(os.path.join(Config.OUTPUT_DIR, f))
                    except OSError as e:
                        print(f"Warning: Could not remove {f}: {e}")
        
        return jsonify({'success': True, 'message': 'Simulation state reset successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def read_shp_pure_python(shp_path):
    """Simple pure-python parser for LineString shapefiles (Type 3)."""
    try:
        with open(shp_path, 'rb') as f:
            f.seek(100)
            geoms = []
            while True:
                header = f.read(8)
                if not header: break
                rec_num, content_len = struct.unpack('>ii', header)
                rec_content = f.read(content_len * 2)
                if not rec_content: break
                shape_type = struct.unpack('<i', rec_content[:4])[0]
                if shape_type == 3: # PolyLine
                    num_parts, num_points = struct.unpack('<ii', rec_content[36:44])
                    parts = struct.unpack('<' + 'i' * num_parts, rec_content[44:44 + num_parts * 4])
                    points_data = rec_content[44 + num_parts * 4:]
                    points = []
                    for i in range(num_points):
                        x, y = struct.unpack('<dd', points_data[i * 16 : (i + 1) * 16])
                        points.append((x, y))
                    if num_parts == 1: geoms.append(LineString(points))
                    else:
                        for i in range(num_parts):
                            start = parts[i]
                            end = parts[i+1] if i+1 < num_parts else num_points
                            geoms.append(LineString(points[start:end]))
                elif shape_type == 1: # Point
                    x, y = struct.unpack('<dd', rec_content[4:20])
                    geoms.append(Point(x, y))
                elif shape_type == 5: # Polygon
                    num_parts, num_points = struct.unpack('<ii', rec_content[36:44])
                    parts = struct.unpack('<' + 'i' * num_parts, rec_content[44:44 + num_parts * 4])
                    points_data = rec_content[44 + num_parts * 4:]
                    points = []
                    for i in range(num_points):
                        x, y = struct.unpack('<dd', points_data[i * 16 : (i + 1) * 16])
                        points.append((x, y))
                    if num_parts == 1: geoms.append(Polygon(points))
                    else: geoms.append(Polygon(points))
            return geoms
    except Exception as e:
        print(f"Error in pure python parser: {e}")
        return []

def read_shapefile_no_gdal(shp_path):
    geoms = read_shp_pure_python(shp_path)
    if not geoms: return None
    df = pd.DataFrame({'id': range(len(geoms))})
    return gpd.GeoDataFrame(df, geometry=geoms)

@data_bp.route('/api/upload-roads', methods=['POST'])
def upload_roads():
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files uploaded. Please select shapefile files.'}), 400
        
        files = request.files.getlist('files[]')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected. Please select shapefile files to upload.'}), 400
        
        road_id = request.form.get('road_id', type=int, default=1)
        custom_crs = request.form.get('crs', Config.DEFAULT_CRS)
        
        road_dir = os.path.join(Config.UPLOAD_DIR, f'road_{road_id}')
        if os.path.exists(road_dir):
            shutil.rmtree(road_dir)
        os.makedirs(road_dir)
        
        saved_files = []
        for f in files:
            if f.filename:
                filepath = os.path.join(road_dir, f.filename)
                f.save(filepath)
                saved_files.append(f.filename)
        
        shp_file = None
        for f in saved_files:
            if f.endswith('.shp'):
                shp_file = f
                break
        
        if not shp_file:
            return jsonify({'error': 'No .shp file found. The .shp file is required for upload.'}), 400
        
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        gdf = gpd.read_file(os.path.join(road_dir, shp_file))
        
        if gdf.crs is None:
            gdf = gdf.set_crs(custom_crs)
        
        session_data = get_session_data()
        if custom_crs != session_data.get('crs', Config.DEFAULT_CRS):
            session_data['crs'] = custom_crs
            state.transformer = Transformer.from_crs(custom_crs, Config.WGS84_CRS, always_xy=True)
            update_session_data({'crs': custom_crs})
        
        gdf = gdf.to_crs(Config.DEFAULT_CRS)
        
        session_data = get_session_data()
        roads = session_data.get('roads', [])
        if len(roads) >= road_id:
            roads[road_id - 1] = gdf
        else:
            while len(roads) < road_id:
                roads.append(None)
            roads[road_id - 1] = gdf
        update_session_data({'roads': roads})
        
        return jsonify({
            'success': True,
            'message': f'Road {road_id} uploaded successfully',
            'road_id': road_id,
            'features': len(gdf),
            'files': saved_files,
            'crs': str(gdf.crs)
        })
    except Exception as e:
        return jsonify({'error': f'Error processing road shapefile: {str(e)}'}), 400

@data_bp.route('/api/upload-weather', methods=['POST'])
def upload_weather():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded.'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected.'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are accepted for weather data.'}), 400
        
        filepath = os.path.join(Config.UPLOAD_DIR, 'weather_data.csv')
        file.save(filepath)
        
        df = pd.read_csv(filepath)
        
        # Normalize column names: map common case variants to expected uppercase
        col_map = {}
        for col in df.columns:
            upper = col.upper()
            if upper in ('MONTH', 'DAY', 'HOUR', 'TEMP_C', 'WS', 'WD', 'YEAR',
                         'CLOUDCOVER_TENTHS', 'RELATIVEHUMIDITY_%', 'STATIONPRESSURE_MB',
                         'CEILINGHEIGHT_M'):
                col_map[col] = upper
        if col_map:
            df.rename(columns=col_map, inplace=True)
        
        required_cols = ['TEMP_C', 'WS', 'WD']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            return jsonify({'error': f'Missing required columns: {missing}'}), 400
        
        if 'MONTH' not in df.columns: df['MONTH'] = 1
        if 'DAY' not in df.columns: df['DAY'] = 1
        if 'HOUR' not in df.columns: df['HOUR'] = 12
        
        update_session_data({'weather_data': df})
        
        return jsonify({
            'success': True,
            'message': 'Weather data uploaded successfully',
            'records': len(df),
            'summary': {
                'avg_temp': float(df['TEMP_C'].mean()),
                'avg_wind_speed': float(df['WS'].mean()),
                'avg_wind_direction': float(df['WD'].mean())
            }
        })
    except Exception as e:
        return jsonify({'error': f'Error processing weather data: {str(e)}'}), 400

@data_bp.route('/api/upload-study-area', methods=['POST'])
def upload_study_area():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files[]')
    custom_crs = request.form.get('crs', Config.DEFAULT_CRS)
    study_dir = os.path.join(Config.UPLOAD_DIR, 'study_area')
    if os.path.exists(study_dir): shutil.rmtree(study_dir)
    os.makedirs(study_dir)
    
    saved_files = []
    for f in files:
        if f.filename:
            filepath = os.path.join(study_dir, f.filename)
            f.save(filepath)
            saved_files.append(f.filename)
    
    try:
        shp_file = next((f for f in saved_files if f.endswith('.shp')), None)
        if not shp_file: return jsonify({'error': 'No .shp file found'}), 400
        
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        gdf = read_shapefile_no_gdal(os.path.join(study_dir, shp_file))
        if gdf is None:
            gdf = gpd.read_file(os.path.join(study_dir, shp_file))
        if gdf.crs is None: gdf = gdf.set_crs(custom_crs)
        
        study_area = gdf.to_crs(Config.DEFAULT_CRS)
        update_session_data({'study_area': study_area})
        
        bounds = study_area.total_bounds
        center_x, center_y = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
        lon, lat = state.transformer.transform(center_x, center_y)
        
        return jsonify({
            'success': True,
            'message': 'Study area uploaded successfully',
            'bounds': list(bounds),
            'center': [lon, lat]
        })
    except Exception as e:
        return jsonify({'error': f'Error processing shapefile: {str(e)}'}), 400

@data_bp.route('/api/upload-pollution', methods=['POST'])
def upload_pollution():
    if 'file' not in request.files: return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    custom_crs = request.form.get('crs', Config.DEFAULT_CRS)
    filepath = os.path.join(Config.UPLOAD_DIR, f'pollution_data.{file.filename.split(".")[-1]}')
    file.save(filepath)
    try:
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath)
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding='latin-1')
        else:
            df = pd.read_excel(filepath)
        if not all(c in df.columns for c in ['POINT_X', 'POINT_Y']):
            return jsonify({'error': 'Missing POINT_X or POINT_Y'}), 400
        update_session_data({'pollution_data': df, 'crs': custom_crs})
        pollutants = [c for c in df.columns if c in ['CO', 'NOx', 'PM10', 'PM2.5', 'PM25']]
        return jsonify({'success': True, 'records': len(df), 'pollutants': pollutants})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@data_bp.route('/api/upload-emission-factors', methods=['POST'])
def upload_emission_factors():
    if 'file' not in request.files: return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    filepath = os.path.join(Config.UPLOAD_DIR, f'emission_factors.{file.filename.split(".")[-1]}')
    file.save(filepath)
    try:
        df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_excel(filepath)
        if not all(c in df.columns for c in ['pollutant', 'emission_factor']):
            return jsonify({'error': 'Missing required columns'}), 400
        factors = df.to_dict('records')
        pollutants = df['pollutant'].unique().tolist()
        update_session_data({'emission_factors': factors})
        return jsonify({
            'success': True, 
            'message': 'Emission factors uploaded successfully',
            'factors': factors,
            'pollutants': pollutants
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@data_bp.route('/api/reset-data', methods=['POST'])
def reset_data():
    default_data = {
        'roads': [],
        'weather_data': None,
        'study_area': None,
        'pollution_data': None,
        'historical_pollution': None,
        'forecast_model': None,
        'emission_factors': None,
        'crs': Config.DEFAULT_CRS
    }
    set_session_data(default_data)
    
    if os.path.exists(Config.UPLOAD_DIR):
        shutil.rmtree(Config.UPLOAD_DIR)
    os.makedirs(Config.UPLOAD_DIR)
    return jsonify({'success': True, 'message': 'All data cleared.'})

@data_bp.route('/api/data-status', methods=['GET'])
def data_status():
    session_data = get_session_data()
    return jsonify({
        'roads': {'count': len(session_data.get('roads', [])), 'loaded': len(session_data.get('roads', [])) > 0},
        'weather': {'loaded': session_data.get('weather_data') is not None},
        'study_area': {'loaded': session_data.get('study_area') is not None},
        'pollution': {'loaded': session_data.get('pollution_data') is not None},
        'crs': session_data.get('crs', Config.DEFAULT_CRS)
    })

@data_bp.route('/api/roads')
def get_roads():
    session_data = get_session_data()
    roads = session_data.get('roads', [])
    if not roads: return jsonify({'success': False, 'message': 'No road data loaded'}), 200
    
    # Roads are always reprojected to DEFAULT_CRS on upload, so always transform from DEFAULT_CRS
    local_transformer = Transformer.from_crs(Config.DEFAULT_CRS, Config.WGS84_CRS, always_xy=True)
    
    roads_geojson = []
    for i, road_gdf in enumerate(roads):
        if road_gdf is None: continue
        for idx, row in road_gdf.iterrows():
            geom = row.geometry
            coords = []
            if geom.geom_type == 'LineString':
                xs, ys = zip(*geom.coords)
                lons, lats = local_transformer.transform(xs, ys)
                coords = list(zip(lons, lats))
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    xs, ys = zip(*line.coords)
                    lons, lats = local_transformer.transform(xs, ys)
                    coords.extend(list(zip(lons, lats)))
            
            bounds = geom.bounds
            center_lon = np.mean([c[0] for c in coords]) if coords else (bounds[0]+bounds[2])/2
            center_lat = np.mean([c[1] for c in coords]) if coords else (bounds[1]+bounds[3])/2
            
            roads_geojson.append({
                'id': i + 1, 'type': 'Feature',
                'properties': {'name': f'Road {i+1}', 'length': geom.length, 'objectid': int(row.get('OBJECTID', i+1))},
                'geometry': {'type': 'LineString', 'coordinates': coords},
                'center': [float(center_lon), float(center_lat)], 'bounds': list(bounds)
            })
    return jsonify(roads_geojson)

@data_bp.route('/api/weather')
def get_weather():
    session_data = get_session_data()
    weather_data = session_data.get('weather_data')
    if weather_data is None: return jsonify({'success': False, 'message': 'No weather data loaded.'}), 200
    
    day, month, hour = request.args.get('day', type=int), request.args.get('month', type=int), request.args.get('hour', type=int)
    
    summary_filtered = weather_data
    if month is not None: summary_filtered = summary_filtered[summary_filtered['MONTH'] == month]
    if day is not None: summary_filtered = summary_filtered[summary_filtered['DAY'] == day]
    if hour is not None: summary_filtered = summary_filtered[summary_filtered['HOUR'] == hour]
    
    if summary_filtered.empty: summary_filtered = weather_data

    # Use filtered data for charts so they reflect the selected month/day/hour
    daily_data = summary_filtered.groupby('DAY').agg({'TEMP_C': 'mean', 'WS': 'mean', 'WD': 'mean'}).reset_index()
    hourly_avg = summary_filtered.groupby('HOUR').agg({'TEMP_C': 'mean', 'WS': 'mean', 'WD': 'mean'}).reset_index()

    # Determine available days for the selected month (for frontend day dropdown)
    if month is not None:
        month_data = weather_data[weather_data['MONTH'] == month]
        available_days = sorted([int(d) for d in month_data['DAY'].unique()])
    else:
        available_days = sorted([int(d) for d in weather_data['DAY'].unique()])

    # Flag to tell frontend whether we're showing daily or hourly view
    is_daily_view = (day is None)

    return jsonify({
        'daily': daily_data.to_dict('records'),
        'hourly': hourly_avg.to_dict('records'),
        'available_months': sorted([int(m) for m in weather_data['MONTH'].unique()]),
        'available_days': available_days,
        'available_hours': sorted([int(h) for h in weather_data['HOUR'].unique()]),
        'is_daily_view': is_daily_view,
        'summary': {
            'avg_temp': float(summary_filtered['TEMP_C'].mean()),
            'avg_wind_speed': float(summary_filtered['WS'].mean()),
            'avg_wind_direction': float(summary_filtered['WD'].mean()),
            'max_wind_speed': float(summary_filtered['WS'].max()),
            'min_wind_speed': float(summary_filtered['WS'].min())
        },
        'selected': {'day': day, 'month': month, 'hour': hour}
    })

@data_bp.route('/api/weather/live', methods=['GET'])
def get_live_weather():
    lat = request.args.get('lat', Config.DEFAULT_LAT, type=float)
    lon = request.args.get('lon', Config.DEFAULT_LON, type=float)
    
    result = fetch_live_weather(lat, lon)
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), result.get('code', 500)

@data_bp.route('/api/pollution/live', methods=['GET'])
def get_live_pollution():
    lat = request.args.get('lat', Config.DEFAULT_LAT, type=float)
    lon = request.args.get('lon', Config.DEFAULT_LON, type=float)
    
    result = fetch_live_pollution(lat, lon)
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), result.get('code', 500)

@data_bp.route('/api/study-area')
def get_study_area():
    session_data = get_session_data()
    study_area = session_data.get('study_area')
    if study_area is None: return jsonify({'success': False, 'message': 'No study area found.'}), 200
    
    # Study area is always reprojected to DEFAULT_CRS on upload, so always transform from DEFAULT_CRS
    local_transformer = Transformer.from_crs(Config.DEFAULT_CRS, Config.WGS84_CRS, always_xy=True)
    
    for idx, row in study_area.iterrows():
        geom = row.geometry
        if geom.geom_type == 'Polygon':
            coords = [local_transformer.transform(x, y) for x, y in geom.exterior.coords]
            return jsonify({
                'type': 'Feature',
                'properties': {'name': 'Study Area'},
                'geometry': {'type': 'Polygon', 'coordinates': [coords]}
            })
    return jsonify({'success': False, 'message': 'No valid study area polygon found'}), 200

@data_bp.route('/api/pollution-data')
def get_pollution_data():
    """Return pollution data as GeoJSON for the map layer."""
    session_data = get_session_data()
    pollution_data = session_data.get('pollution_data')
    if pollution_data is None:
        return jsonify({'type': 'FeatureCollection', 'features': []})
    
    crs = session_data.get('crs', Config.DEFAULT_CRS)
    local_transformer = Transformer.from_crs(crs, Config.WGS84_CRS, always_xy=True)
    
    features = []
    for idx, row in pollution_data.iterrows():
        try:
            x, y = row['POINT_X'], row['POINT_Y']
            lon, lat = local_transformer.transform(x, y)
            props = {col: float(row[col]) if isinstance(row[col], (int, float)) and not np.isnan(row[col]) else 0
                     for col in row.index if col not in ['POINT_X', 'POINT_Y', 'geometry']}
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                'properties': props
            })
        except Exception:
            continue
    
    return jsonify({'type': 'FeatureCollection', 'features': features})

def initialize_default_data():
    """
    Called on startup to automatically load data files existing in the root directory.
    """
    print("Initializing default data...")
    
    # 1. Load Roads (road1.shp to road4.shp)
    for i in range(1, 5):
        shp_path = os.path.join(Config.DATA_DIR, f'road{i}.shp')
        print(f"  Attempting to load {shp_path}...")
        if os.path.exists(shp_path):
            try:
                gdf = read_shapefile_no_gdal(shp_path)
                if gdf is None: gdf = gpd.read_file(shp_path)
                if gdf.crs is None:
                    gdf = gdf.set_crs(Config.DEFAULT_CRS)
                
                # Re-project to internal CRS if needed (though road*.shp are likely already in Zone 38N)
                gdf = gdf.to_crs(Config.DEFAULT_CRS)
                
                session_data = get_session_data()
                roads = session_data.get('roads', [])
                while len(roads) < i:
                    roads.append(None)
                roads[i-1] = gdf
                update_session_data({'roads': roads})
                print(f"  [OK] Road {i} loaded.")
            except Exception as e:
                print(f"  [ERROR] Failed to load road{i}.shp: {e}")

    # 2. Load Weather (ERA5_P0INTS.csv)
    weather_path = os.path.join(Config.DATA_DIR, 'ERA5_P0INTS.csv')
    if os.path.exists(weather_path):
        try:
            df = pd.read_csv(weather_path)
            # Normalize column names: map common case variants to expected uppercase
            col_map = {}
            for col in df.columns:
                upper = col.upper()
                if upper in ('MONTH', 'DAY', 'HOUR', 'TEMP_C', 'WS', 'WD', 'YEAR',
                             'CLOUDCOVER_TENTHS', 'RELATIVEHUMIDITY_%', 'STATIONPRESSURE_MB',
                             'CEILINGHEIGHT_M'):
                    col_map[col] = upper
            if col_map:
                df.rename(columns=col_map, inplace=True)
            if all(c in df.columns for c in ['TEMP_C', 'WS', 'WD']):
                if 'MONTH' not in df.columns: df['MONTH'] = 1
                if 'DAY' not in df.columns: df['DAY'] = 1
                if 'HOUR' not in df.columns: df['HOUR'] = 12
                
                update_session_data({'weather_data': df})
                print("  [OK] Weather data loaded.")
            else:
                print("  [WARNING] ERA5_P0INTS.csv missing required columns.")
        except Exception as e:
            print(f"  [ERROR] Failed to load ERA5_P0INTS.csv: {e}")

    # 2. Load Study Area (study_area.shp)
    shp_path = os.path.join(Config.DATA_DIR, 'study_area.shp')
    print(f"  Attempting to load study area: {shp_path}...")
    if os.path.exists(shp_path):
        try:
            gdf = read_shapefile_no_gdal(shp_path)
            if gdf is None: gdf = gpd.read_file(shp_path)
            if gdf.crs is None:
                gdf = gdf.set_crs(Config.DEFAULT_CRS)
            gdf = gdf.to_crs(Config.DEFAULT_CRS)
            update_session_data({'study_area': gdf})
            print("  [OK] Study area loaded.")
        except Exception as e:
            print(f"  [ERROR] Failed to load study_area.shp: {e}")

    # 3. Load Pollution Data (pollution_results.csv or Hotspots_AllPollutants_GIS.csv)

    pollution_files = ['pollution_results.csv', 'Hotspots_AllPollutants_GIS.csv']
    for p_file in pollution_files:
        p_path = os.path.join(Config.DATA_DIR, p_file)
        print(f"  Attempting to load pollution data: {p_path}...")
        if os.path.exists(p_path):
            try:
                df = pd.read_csv(p_path)
                if 'POINT_X' in df.columns and 'POINT_Y' in df.columns:
                    with data_lock:
                        session_data['pollution_data'] = df
                    print(f"  [OK] Pollution data ({p_file}) loaded.")
                    break
            except Exception as e:
                print(f"  [ERROR] Failed to load {p_file}: {e}")
