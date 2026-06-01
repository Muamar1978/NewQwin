from flask import Blueprint, request, jsonify, send_file
import os
import json
import requests
import uuid
import zipfile
from datetime import datetime
from config import Config
from state import session_data, data_lock
from gaussian_model import GaussianPlumeModel
from services.weather_service import fetch_live_weather

sim_bp = Blueprint('simulation', __name__)

@sim_bp.route('/api/simulate', methods=['POST'])
def simulate():
    roads = session_data.get('roads', [])
    weather_data = session_data.get('weather_data')
    if not roads or weather_data is None:
        return jsonify({'error': 'Data not loaded.'}), 500
    
    # Ensure output directory exists
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    
    data = request.json
    road_ids = data.get('road_ids', [1])
    if isinstance(road_ids, int): road_ids = [road_ids]
    elif isinstance(road_ids, str): road_ids = [int(road_ids)]
    
    pollutant = data.get('pollutant', 'NOx')
    try:
        traffic_count = int(data.get('traffic_count', 1000))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid traffic count value'}), 400
    day, month, hour = data.get('day'), data.get('month'), data.get('hour')
    try:
        buffer_distance = int(data.get('buffer_distance', 250))
    except (TypeError, ValueError):
        buffer_distance = 250
        
    try:
        bg_conc = float(data.get('background_concentration', 0.0))
    except (TypeError, ValueError):
        bg_conc = 0.0
    
    model = GaussianPlumeModel(roads, weather_data, session_data.get('emission_factors'))
    
    # Handle Live Weather Integration
    live_params = {}
    if data.get('live'):
        weather_res = fetch_live_weather()
        if weather_res.get('success'):
            live_data = weather_res.get('summary', {})
            live_params = {
                'live_ws': live_data.get('avg_wind_speed'),
                'live_wd': live_data.get('avg_wind_direction'),
                'live_temp': live_data.get('avg_temp')
            }
        else:
            print(f"Warning: Live weather fetch failed: {weather_res.get('error')}")

    results, params = model.run_simulation(road_ids, pollutant, traffic_count, day, month, hour, buffer_distance, background_concentration=bg_conc, **live_params)
    
    result_id = str(uuid.uuid4())
    # Pre-calculate max concentration using NumPy for speed
    all_concs = [r['concentration'] for r in results]
    max_c = float(max(all_concs)) if all_concs else 0.0
    
    with data_lock:
        session_data['simulation_results'].append({
            'id': result_id, 'road_ids': road_ids, 'pollutant': pollutant,
            'traffic_count': traffic_count, 'buffer_distance': buffer_distance,
            'max_concentration': max_c,
            'timestamp': datetime.now().isoformat()
        })
        # Limit history to latest 20 entries to prevent memory bloat
        if len(session_data['simulation_results']) > 20:
            session_data['simulation_results'] = session_data['simulation_results'][-20:]
    
    road_label = '-'.join(map(str, road_ids))
    output_path = os.path.join(Config.OUTPUT_DIR, f'concentration_roads{road_label}.geojson')
    
    features = [{
        'type': 'Feature',
        'properties': {'concentration': round(r['concentration'], 8), 'pollutant': r['pollutant']},
        'geometry': {'type': 'Point', 'coordinates': [r['lon'], r['lat']]}
    } for r in results if r['concentration'] > 0]
    
    geojson = {'type': 'FeatureCollection', 'features': features}
    with open(output_path, 'w') as f:
        json.dump(geojson, f)
    
    if not results: return jsonify({'error': 'No simulation results generated'}), 500
    
    full_max = float(params.get('full_max_concentration', 0))
    max_conc = full_max if full_max > 0 else max_c
    
    return jsonify({
        'concentrations': geojson,
        'parameters': params,
        'max_concentration': max_conc,
        'output_path': output_path,
        'grid': {
            'x_min': float(min([r['x'] for r in results])) if results else 0.0,
            'x_max': float(max([r['x'] for r in results])) if results else 0.0,
            'y_min': float(min([r['y'] for r in results])) if results else 0.0,
            'y_max': float(max([r['y'] for r in results])) if results else 0.0,
            'conc_min': float(min([r['concentration'] for r in results])) if results else 0.0,
            'conc_max': float(max_conc)
        }
    })

@sim_bp.route('/api/simulation-history', methods=['GET'])
def simulation_history():
    results = session_data.get('simulation_results', [])
    return jsonify({'count': len(results), 'results': results})

@sim_bp.route('/api/simulation-history/<result_id>', methods=['DELETE'])
def delete_simulation_result(result_id):
    with data_lock:
        session_data['simulation_results'] = [r for r in session_data.get('simulation_results', []) if r.get('id') != result_id]
    return jsonify({'success': True, 'message': f'Deleted result {result_id}'})

@sim_bp.route('/api/clear-history', methods=['POST'])
def clear_simulation_history():
    with data_lock:
        session_data['simulation_results'] = []
    return jsonify({'success': True, 'message': 'History cleared'})

@sim_bp.route('/api/shapefile', methods=['POST'])
def create_shapefile():
    roads = session_data.get('roads', [])
    weather_data = session_data.get('weather_data')
    if not roads or weather_data is None: return jsonify({'error': 'Data not loaded'}), 500
    
    data = request.json
    road_ids = data.get('road_ids', [1])
    if isinstance(road_ids, int): road_ids = [road_ids]
    elif isinstance(road_ids, str): road_ids = [int(road_ids)]
    
    pollutant = data.get('pollutant', 'NOx')
    try:
        traffic_count = int(data.get('traffic_count', 1000))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid traffic count value'}), 400
    day, month, hour = data.get('day'), data.get('month'), data.get('hour')
    try:
        buffer_distance = int(data.get('buffer_distance', 250))
    except (TypeError, ValueError):
        buffer_distance = 250
        
    try:
        bg_conc = float(data.get('background_concentration', 0.0))
    except (TypeError, ValueError):
        bg_conc = 0.0
    
    model = GaussianPlumeModel(roads, weather_data, session_data.get('emission_factors'))
    results, params = model.run_simulation(road_ids, pollutant, traffic_count, day, month, hour, buffer_distance, background_concentration=bg_conc)
    
    road_label = '-'.join(map(str, road_ids))
    shp_path = os.path.join(Config.OUTPUT_DIR, f'pollution_roads{road_label}.shp')
    model.create_concentration_shapefile(results, shp_path)
    
    base = shp_path[:-4]
    zip_path = os.path.join(Config.OUTPUT_DIR, f'pollution_roads{road_label}.zip')
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for ext in ['.shp', '.shx', '.dbf', '.prj']:
            fpath = base + ext
            if os.path.exists(fpath): zf.write(fpath, os.path.basename(fpath))
    
    return jsonify({'shapefile_path': shp_path, 'zip_path': os.path.basename(zip_path), 'record_count': len(results)})
