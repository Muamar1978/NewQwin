from flask_caching import Cache
import json
import os
from config import Config

# Initialize Flask-Caching with filesystem backend for thread-safe state management
cache = Cache(config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': os.path.join(Config.DATA_DIR, 'cache'),
    'CACHE_DEFAULT_TIMEOUT': 3600  # 1 hour default timeout
})

def get_session_data(session_id='default'):
    """Get session data from cache."""
    key = f'session_{session_id}'
    data = cache.get(key)
    if data is None:
        # Initialize default session data if not exists
        data = {
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
        cache.set(key, data)
    return data

def set_session_data(data, session_id='default'):
    """Set session data in cache."""
    key = f'session_{session_id}'
    cache.set(key, data)

def update_session_data(updates, session_id='default'):
    """Update specific fields in session data."""
    data = get_session_data(session_id)
    data.update(updates)
    set_session_data(data, session_id)
    return data

# Shared transformer - will be created dynamically based on CRS
def get_transformer(crs=None):
    """Get transformer for the specified CRS."""
    from pyproj import Transformer
    if crs is None:
        crs = Config.DEFAULT_CRS
    return Transformer.from_crs(crs, Config.WGS84_CRS, always_xy=True)
