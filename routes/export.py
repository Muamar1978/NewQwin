from flask import Blueprint, request, jsonify, send_file
import os
import pandas as pd
from datetime import datetime
from config import Config
from state import get_session_data
from models.gaussian_model import GaussianPlumeModel

export_bp = Blueprint('export', __name__)

@export_bp.route('/output/<filename>')
def serve_output(filename):
    return send_file(os.path.join(Config.OUTPUT_DIR, filename))

@export_bp.route('/api/export-excel', methods=['POST'])
def export_excel():
    session_data = get_session_data()
    roads = session_data.get('roads', [])
    weather_data = session_data.get('weather_data')
    if not roads or weather_data is None: return jsonify({'error': 'Data not loaded'}), 500
    
    data = request.json or {}
    road_ids = data.get('road_ids', [1])
    if isinstance(road_ids, int): road_ids = [road_ids]
    elif isinstance(road_ids, str): road_ids = [int(road_ids)]
    
    pollutant = data.get('pollutant', 'NOx')
    traffic_count = int(data.get('traffic_count', 1000))
    day, month, hour = data.get('day'), data.get('month'), data.get('hour')
    buffer_distance = data.get('buffer_distance', 250)
    
    weather_filtered = weather_data
    if hour is not None: weather_filtered = weather_filtered[weather_filtered['HOUR'] == hour]
    if month is not None: weather_filtered = weather_filtered[weather_filtered['MONTH'] == month]
    if day is not None: weather_filtered = weather_filtered[weather_filtered['DAY'] == day]
    if weather_filtered.empty: weather_filtered = weather_data
    
    road_label = '-'.join(map(str, road_ids))
    date_label = f"m{month or 'all'}_d{day or 'all'}_h{hour or 'all'}_b{buffer_distance}"
    excel_filename = f'kirkuk_air_quality_{date_label}_r{road_label}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    excel_path = os.path.join(Config.OUTPUT_DIR, excel_filename)
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        if not weather_filtered.empty:
            weather_filtered.to_excel(writer, sheet_name='Weather Data', index=False)
            weather_filtered.groupby('DAY').agg({'TEMP_C': 'mean', 'WS': 'mean', 'WD': 'mean'}).reset_index().to_excel(writer, sheet_name='Daily Summary', index=False)
            weather_filtered.groupby('HOUR').agg({'TEMP_C': 'mean', 'WS': 'mean', 'WD': 'mean'}).reset_index().to_excel(writer, sheet_name='Hourly Summary', index=False)
        
        if roads:
            roads_info = []
            for i, road_gdf in enumerate(roads):
                if road_gdf is None: continue
                for idx, row in road_gdf.iterrows():
                    roads_info.append({'Road ID': i + 1, 'Length (m)': round(row.geometry.length, 2), 'OBJECTID': int(row.get('OBJECTID', i+1))})
            if roads_info: pd.DataFrame(roads_info).to_excel(writer, sheet_name='Roads Info', index=False)
        
        try:
            if os.path.exists('pollution_results.csv'):
                pd.read_csv('pollution_results.csv').to_excel(writer, sheet_name='Existing Pollution Data', index=False)
        except Exception:
            pass
        
        model = GaussianPlumeModel(roads, weather_data, session_data.get('emission_factors'))
        results, params = model.run_simulation(road_ids, pollutant, traffic_count, day, month, hour, buffer_distance)
        
        res_df = pd.DataFrame(results)
        if not res_df.empty:
            res_df = res_df.rename(columns={'lon': 'Longitude', 'lat': 'Latitude', 'x': 'X (m)', 'y': 'Y (m)', 'concentration': 'Concentration (µg/m³)', 'pollutant': 'Pollutant'})
            res_df.to_excel(writer, sheet_name='Simulation Results', index=False)
        
        # Remove heatmap from params as it is too large for Excel cells
        params_for_excel = params.copy()
        if isinstance(params_for_excel, dict):
            params_for_excel.pop('heatmap', None)
        
        pd.DataFrame([params_for_excel]).to_excel(writer, sheet_name='Simulation Parameters', index=False)
        
    return send_file(excel_path, as_attachment=True, download_name=excel_filename)
