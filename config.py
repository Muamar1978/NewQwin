import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024
    UPLOAD_FOLDER = 'uploads'
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
    UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
    DEFAULT_CRS = "EPSG:4326"  # WGS84 as safe default
    WGS84_CRS = "EPSG:4326"
    
    # Live Weather Integration - Load API key from environment variable
    WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
    DEFAULT_LAT = 35.4673
    DEFAULT_LON = 44.3917
    WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
    POLLUTION_API_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
