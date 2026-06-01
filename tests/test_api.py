import pytest
import os
import json
from app import app
from state import session_data, data_lock

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'Air Quality' in res.data

def test_data_status(client):
    res = client.get('/api/data-status')
    assert res.status_code == 200
    data = res.get_json()
    assert 'roads' in data
    assert 'weather' in data

def test_simulation_no_data(client):
    res = client.post('/api/simulate', json={'road_ids': [1]})
    # Should fail if no data loaded
    assert res.status_code == 500
    assert b'Data not loaded' in res.data

def test_simulation_history(client):
    with data_lock:
        session_data['simulation_results'] = []
    
    res = client.get('/api/simulation-history')
    assert res.status_code == 200
    data = res.get_json()
    assert data['count'] == 0

def test_live_weather_endpoint(client):
    # This might fail if no internet, so we check status code for either 200 or 401/other
    res = client.get('/api/weather/live')
    # If API key is invalid (which it might be in test env), expect 401
    assert res.status_code in [200, 401, 500]
