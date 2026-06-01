import requests
from config import Config

def fetch_live_weather(lat=Config.DEFAULT_LAT, lon=Config.DEFAULT_LON):
    """
    Fetch live weather data from OpenWeatherMap API and map it to internal format.
    """
    try:
        params = {
            'lat': lat,
            'lon': lon,
            'appid': Config.WEATHER_API_KEY,
            'units': 'metric'
        }
        
        response = requests.get(Config.WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            'success': True,
            'summary': {
                'avg_temp': data['main']['temp'],
                'avg_wind_speed': data['wind']['speed'],
                'avg_wind_direction': data['wind']['deg'],
                'description': data['weather'][0]['description'],
                'city': data.get('name', 'Kirkuk Area'),
                'timestamp': data['dt']
            },
            'live': True
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = 'Invalid or inactive OpenWeatherMap API key.' if status_code == 401 else f'Weather service error: {str(e)}'
        return {'success': False, 'error': error_msg, 'code': status_code}
    except Exception as e:
        return {'success': False, 'error': f'Failed to fetch live weather: {str(e)}'}

def fetch_live_pollution(lat=Config.DEFAULT_LAT, lon=Config.DEFAULT_LON):
    """
    Fetch live pollution data from OpenWeatherMap API and map it to internal format.
    """
    try:
        params = {
            'lat': lat,
            'lon': lon,
            'appid': Config.WEATHER_API_KEY
        }
        
        response = requests.get(Config.POLLUTION_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('list'):
            return {'success': False, 'error': 'No pollution data returned from service.', 'code': 404}
            
        pollution_data = data['list'][0]
        
        return {
            'success': True,
            'summary': {
                'aqi': pollution_data['main']['aqi'],
                'co': pollution_data['components']['co'],
                'no': pollution_data['components']['no'],
                'no2': pollution_data['components']['no2'],
                'o3': pollution_data['components']['o3'],
                'so2': pollution_data['components']['so2'],
                'pm2_5': pollution_data['components']['pm2_5'],
                'pm10': pollution_data['components']['pm10'],
                'nh3': pollution_data['components']['nh3'],
                'timestamp': pollution_data['dt']
            },
            'live': True
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = 'Invalid or inactive OpenWeatherMap API key.' if status_code == 401 else f'Pollution service error: {str(e)}'
        return {'success': False, 'error': error_msg, 'code': status_code}
    except Exception as e:
        return {'success': False, 'error': f'Failed to fetch live pollution: {str(e)}'}
