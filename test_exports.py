import requests
import os

URL = "http://localhost:5000"

def upload_roads():
    print("Uploading roads...")
    # We can use the existing road1.shp etc.
    # But the API expects files[]
    files = [
        ('files[]', ('road1.shp', open('road1.shp', 'rb'), 'application/octet-stream')),
        ('files[]', ('road1.shx', open('road1.shx', 'rb'), 'application/octet-stream')),
        ('files[]', ('road1.dbf', open('road1.dbf', 'rb'), 'application/octet-stream')),
        ('files[]', ('road1.prj', open('road1.prj', 'rb'), 'application/octet-stream')),
    ]
    data = {'road_id': 1, 'crs': 'EPSG:32638'}
    r = requests.post(f"{URL}/api/upload-roads", files=files, data=data)
    print(f"Roads upload: {r.status_code} {r.text}")

def upload_weather():
    print("Uploading weather...")
    # Create a dummy weather csv
    with open('test_weather.csv', 'w') as f:
        f.write("MONTH,DAY,HOUR,TEMP_C,WS,WD\n12,15,12,15.0,5.0,270\n")
    
    files = {'file': open('test_weather.csv', 'rb')}
    r = requests.post(f"{URL}/api/upload-weather", files=files)
    print(f"Weather upload: {r.status_code} {r.text}")

def test_export_excel():
    print("Testing export excel...")
    data = {
        'road_ids': [1],
        'pollutant': 'NOx',
        'traffic_count': 1000,
        'day': 15,
        'month': 12,
        'hour': 12,
        'buffer_distance': 250
    }
    r = requests.post(f"{URL}/api/export-excel", json=data)
    print(f"Export excel: {r.status_code}")
    if r.status_code != 200:
        print(f"Error: {r.text}")

def test_export_ai():
    print("Testing export ai...")
    data = {
        'road_ids': [1],
        'pollutant': 'NOx',
        'traffic_count': 1000,
        'day': 15,
        'month': 12,
        'hour': 12,
        'buffer_distance': 250
    }
    r = requests.post(f"{URL}/api/export-ai-csv", json=data)
    print(f"Export ai: {r.status_code}")
    if r.status_code != 200:
        print(f"Error: {r.text}")

if __name__ == "__main__":
    try:
        upload_roads()
        upload_weather()
        test_export_excel()
        test_export_ai()
    except Exception as e:
        print(f"Script failed: {e}")
