import threading
from pyproj import Transformer
from config import Config

data_lock = threading.Lock()

session_data = {
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

# Shared transformer that can be updated
transformer = Transformer.from_crs(Config.DEFAULT_CRS, Config.WGS84_CRS, always_xy=True)
