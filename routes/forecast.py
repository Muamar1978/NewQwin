from flask import Blueprint, request, jsonify, send_file
import os
import pandas as pd
import numpy as np
import zipfile
from datetime import datetime
from config import Config
from state import session_data, data_lock
from forecast_model import AirQualityForecastModel
from gaussian_model import GaussianPlumeModel
import geopandas as gpd
# from sklearn.preprocessing import MinMaxScaler

forecast_bp = Blueprint('forecast', __name__)

@forecast_bp.route('/api/forecast', methods=['GET'])
def get_forecast():
    model = session_data.get('forecast_model')
    if not model or not model.is_trained:
        return jsonify({'error': 'Model not trained. Please train the model first.'}), 400
    
    hours = request.args.get('hours', default=24, type=int)
    historical_data = session_data.get('historical_pollution')
    if historical_data is None:
        return jsonify({'error': 'No historical data available for prediction.'}), 400
    
    try:
        results = model.forecast_from_data(historical_data, session_data.get('weather_data'), hours)
        
        # Inject coordinates if available so that shapefile exports work
        coord_df = session_data.get('coordinate_data', pd.DataFrame())
        lon, lat, mx, my = 0.0, 0.0, 0.0, 0.0
        if not coord_df.empty:
            if 'Longitude' in coord_df.columns:
                lon = coord_df['Longitude'].iloc[0]
                lat = coord_df['Latitude'].iloc[0]
            mx = coord_df['X (m)'].iloc[0] if 'X (m)' in coord_df.columns else 0.0
            my = coord_df['Y (m)'].iloc[0] if 'Y (m)' in coord_df.columns else 0.0
            
        for res in results:
            res['Longitude'] = float(lon)
            res['Latitude'] = float(lat)
            res['X (m)'] = float(mx)
            res['Y (m)'] = float(my)
            
        with data_lock:
            session_data['last_forecast'] = {
                'predictions': results,
                'pollutants': model.pollutants,
                'pollutant_name': session_data.get('pollutant_name', 'Unknown')
            }
            
        return jsonify({
            'success': True,
            'predictions': results,
            'pollutants': model.pollutants,
            'model_type': 'LSTM-TFT',
            'forecast_horizon': model.forecast_horizon
        })
    except Exception as e:
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500

@forecast_bp.route('/api/forecast/status', methods=['GET'])
def get_forecast_status():
    model = session_data.get('forecast_model')
    return jsonify({
        'has_historical_data': session_data.get('historical_pollution') is not None,
        'has_weather_data': session_data.get('weather_data') is not None,
        'model_trained': model.is_trained if model else False,
        'model_info': model.get_model_info() if model else {}
    })

@forecast_bp.route('/api/forecast-shapefile', methods=['POST'])
def export_forecast_shapefile():
    forecast_data = session_data.get('last_forecast')
    if not forecast_data: return jsonify({'error': 'No forecast data available.'}), 400
    
    predictions = forecast_data.get('predictions', [])
    if not predictions: return jsonify({'error': 'No predictions available.'}), 400
    
    try:
        features = []
        for pred in predictions:
            lon, lat = pred.get('Longitude'), pred.get('Latitude')
            if lon is None or lat is None or (lon == 0 and lat == 0): continue
            
            pollutant_vals = pred.get('pollutant_values', {})
            if not pollutant_vals and 'concentration' in pred:
                pollutant_vals = {'Concentration': pred.get('concentration', 0)}
            
            feature = {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                'properties': {
                    'timestamp': pred.get('timestamp', ''),
                    'Concentration': pred.get('concentration', 0),
                    'pollutant': forecast_data.get('pollutant_name', 'Unknown')
                }
            }
            feature['properties'].update(pollutant_vals)
            features.append(feature)
        
        if not features: return jsonify({'error': 'No valid coordinates.'}), 400
        
        gdf = gpd.GeoDataFrame.from_features(features)
        gdf = gdf.set_crs("EPSG:4326")
        shp_path = os.path.join(Config.OUTPUT_DIR, 'forecast_predictions.shp')
        gdf.to_file(shp_path)
        
        zip_path = os.path.join(Config.OUTPUT_DIR, 'forecast_predictions.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                fpath = shp_path[:-4] + ext
                if os.path.exists(fpath): zf.write(fpath, os.path.basename(fpath))
        
        return jsonify({'success': True, 'shapefile_path': shp_path, 'zip_path': os.path.basename(zip_path), 'record_count': len(features)})
    except Exception as e:
        return jsonify({'error': f'Failed to export shapefile: {str(e)}'}), 500

@forecast_bp.route('/api/upload-historical', methods=['POST'])
def upload_historical():
    if 'file' not in request.files: return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'): return jsonify({'error': 'Only CSV accepted'}), 400
    
    try:
        try:
            df = pd.read_csv(file)
        except UnicodeDecodeError:
            file.seek(0)
            df = pd.read_csv(file, encoding='latin-1')
        if df.empty: return jsonify({'error': 'CSV is empty.'}), 400
        
        required = ['timestamp', 'X (m)', 'Y (m)']
        if not all(c in df.columns for c in required): return jsonify({'error': 'Missing required columns'}), 400
        
        # Fuzzy match for concentration column
        conc_col = None
        for c in df.columns:
            if 'concentration' in c.lower():
                conc_col = c
                break
        if conc_col is None: return jsonify({'error': 'Missing Concentration column (could not find any column containing "concentration")'}), 400
        
        df = df.rename(columns={conc_col: 'Concentration'})
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp']).sort_values('timestamp')
        df['Concentration'] = pd.to_numeric(df['Concentration'], errors='coerce')
        df = df[df['Concentration'] > 0]
        
        df['hour'], df['day'], df['month'] = df['timestamp'].dt.hour, df['timestamp'].dt.day, df['timestamp'].dt.month
        
        coord_df = df[['Longitude', 'Latitude', 'X (m)', 'Y (m)']].copy() if 'Longitude' in df.columns else pd.DataFrame()
        if coord_df.empty:
            coord_df = pd.DataFrame({'Longitude': 0.0, 'Latitude': 0.0, 'X (m)': df['X (m)'], 'Y (m)': df['Y (m)']})

        pollutant_name = df['Pollutant'].iloc[0] if 'Pollutant' in df.columns else 'Unknown'
        
        with data_lock:
            session_data['historical_pollution'] = df
            session_data['coordinate_data'] = coord_df
            session_data['pollutant_name'] = pollutant_name
            
        return jsonify({'success': True, 'records': len(df), 'pollutant': pollutant_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@forecast_bp.route('/api/forecast/train', methods=['POST'])
def train_forecast():
    data = request.json or {}
    seq_len = data.get('sequence_length', 12)
    horizon = data.get('forecast_horizon', 6)
    epochs = data.get('epochs', 10)
    batch_size = data.get('batch_size', 16)
    
    if session_data.get('historical_pollution') is None:
        return jsonify({'error': 'No historical data.'}), 400
    
    df = session_data['historical_pollution'].copy()
    weather = session_data.get('weather_data')
    
    model = AirQualityForecastModel(sequence_length=seq_len, forecast_horizon=horizon)
    if not model.get_model_info()['tensorflow_available']:
        return jsonify({'error': 'TensorFlow not installed.'}), 500
    
    try:
        print(f"DEBUG: Starting training with {len(df)} records and sequence_length={seq_len}")
        results = model.train(df, weather, epochs=epochs, batch_size=batch_size)
        print(f"DEBUG: Training completed successfully. Results: {results}")
        with data_lock:
            session_data['forecast_model'] = model
        return jsonify({'success': True, **results})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Training failed: {str(e)}', 'val_rmse': None}), 500

@forecast_bp.route('/api/export-ai-csv', methods=['POST'])
def export_ai_csv():
    roads = session_data.get('roads', [])
    weather_data = session_data.get('weather_data')
    if not roads or weather_data is None: return jsonify({'error': 'Data not loaded. Please upload roads and weather data.'}), 500
    
    try:
        data = request.json or {}
        road_ids = data.get('road_ids', [1])
        if isinstance(road_ids, int): road_ids = [road_ids]
        elif isinstance(road_ids, str): road_ids = [int(road_ids)]
        
        traffic_count = int(data.get('traffic_count', 1000))
        day, month, hour = data.get('day'), data.get('month'), data.get('hour')
        buffer_distance = data.get('buffer_distance', 250)
        pollutant = data.get('pollutant', 'NOx')
        
        weather_filtered = weather_data
        if hour is not None: weather_filtered = weather_filtered[weather_filtered['HOUR'] == hour]
        if month is not None: weather_filtered = weather_filtered[weather_filtered['MONTH'] == month]
        if day is not None: weather_filtered = weather_filtered[weather_filtered['DAY'] == day]
        if weather_filtered.empty: weather_filtered = weather_data
        
        model = GaussianPlumeModel(roads, weather_data, session_data.get('emission_factors'))
        results, params = model.run_simulation(road_ids, pollutant, traffic_count, day, month, hour, buffer_distance)
        
        if not results or len(results) == 0:
            return jsonify({'error': 'No simulation results generated. Try increasing buffer distance or checking road selection.'}), 500
        
        from datetime import timedelta
        base_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        ai_data = []
        # Generate 168 hours (7 days) of synthetic historical data backwards
        for i in range(168):
            ts_time = base_time - timedelta(hours=167 - i)
            # Add a diurnal multiplier to simulate day/night pollution cycles for the AI to learn
            factor = 1.0 + 0.3 * np.sin(2 * np.pi * (ts_time.hour - 6) / 24)
            for r in results:
                ai_data.append({
                    'timestamp': ts_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'Longitude': round(r['lon'], 6), 'Latitude': round(r['lat'], 6),
                    'X (m)': round(r['x'], 2), 'Y (m)': round(r['y'], 2),
                    'Concentration (µg/m³)': round(r.get('concentration', 0) * factor, 8), 
                    'Pollutant': pollutant
                })
        
        df = pd.DataFrame(ai_data)
        road_label = '-'.join(map(str, road_ids))
        csv_filename = f'ai_historical_data_r{road_label}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        csv_path = os.path.join(Config.OUTPUT_DIR, csv_filename)
        df.to_csv(csv_path, index=False)
        return send_file(csv_path, as_attachment=True, download_name=csv_filename)
        
    except Exception as e:
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500


@forecast_bp.route('/api/export-forecast-format', methods=['POST'])
def export_forecast_format():
    roads = session_data.get('roads', [])
    weather_data = session_data.get('weather_data')
    if not roads or weather_data is None: return jsonify({'error': 'Data not loaded.'}), 400
    
    data = request.json or {}
    road_ids = data.get('road_ids', [1])
    if isinstance(road_ids, int): road_ids = [road_ids]
    elif isinstance(road_ids, str): road_ids = [int(road_ids)]
    
    pollutant = data.get('pollutant', 'NOx')
    traffic_count = int(data.get('traffic_count', 1000))
    day, month, hour = data.get('day'), data.get('month'), data.get('hour')
    buffer_distance = data.get('buffer_distance', 250)
    
    model = GaussianPlumeModel(roads, weather_data, session_data.get('emission_factors'))
    results, params = model.run_simulation(road_ids, pollutant, traffic_count, day, month, hour, buffer_distance)
    
    if not results: return jsonify({'error': 'No results generated.'}), 400
    
    export_data = []
    for r in results:
        timestamp = f"{datetime.now().year}-{(month if month is not None else 12):02d}-{(day if day is not None else 1):02d} {(hour if hour is not None else 12):02d}:00:00"
        export_data.append({
            'timestamp': timestamp,
            'CO': round(r.get('concentration', 0) * 3.0, 4),
            'NOx': round(r.get('concentration', 0), 4),
            'PM10': round(r.get('concentration', 0) * 0.7, 4),
            'PM2.5': round(r.get('concentration', 0) * 0.35, 4)
        })
    
    df = pd.DataFrame(export_data)
    csv_path = os.path.join(Config.OUTPUT_DIR, f'forecast_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)
