import pytest
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from gaussian_model import GaussianPlumeModel

@pytest.fixture
def mock_weather():
    return pd.DataFrame({
        'TEMP_C': [25.0, 20.0],
        'WS': [2.5, 3.0],
        'WD': [180.0, 190.0],
        'MONTH': [1, 1],
        'DAY': [1, 1],
        'HOUR': [12, 13]
    })

@pytest.fixture
def mock_roads():
    # Simple UTM Zone 38N coordinates (Kirkuk area roughly)
    line = LineString([(444000, 3925000), (445000, 3925000)])
    gdf = gpd.GeoDataFrame({'geometry': [line]}, crs="EPSG:32638")
    return [gdf]

def test_stability_class(mock_roads, mock_weather):
    model = GaussianPlumeModel(mock_roads, mock_weather)
    
    # Day cases
    assert model.calculate_stability_class(1.5, is_day=True, solar_radiation='strong') == 'A'
    assert model.calculate_stability_class(4.0, is_day=True, solar_radiation='moderate') == 'B'
    assert model.calculate_stability_class(7.0, is_day=True, solar_radiation='slight') == 'D'
    
    # Night cases
    assert model.calculate_stability_class(1.5, is_day=False, cloud_cover=0.1) == 'F'
    assert model.calculate_stability_class(2.5, is_day=False, cloud_cover=0.1) == 'E'

def test_concentration_basic(mock_roads, mock_weather):
    model = GaussianPlumeModel(mock_roads, mock_weather)
    
    # Test ground level concentration
    # x, y, z, source_x, source_y, wind_speed, wind_dir, emission_rate, stability_class
    conc = model.calculate_concentration(
        x=100, y=0, z=0,
        source_x=0, source_y=0,
        wind_speed=2.0, wind_dir=270, # Wind from West to East
        emission_rate=1.0,
        stability_class='C'
    )
    
    assert conc > 0
    # Further away should be lower
    conc_far = model.calculate_concentration(
        x=500, y=0, z=0,
        source_x=0, source_y=0,
        wind_speed=2.0, wind_dir=270,
        emission_rate=1.0,
        stability_class='C'
    )
    assert conc_far < conc

def test_simulation_run(mock_roads, mock_weather):
    model = GaussianPlumeModel(mock_roads, mock_weather)
    results, params = model.run_simulation(road_ids=[1], pollutant='NOx', traffic_count=1000)
    
    assert len(results) > 0
    assert 'full_max_concentration' in params
    assert 'heatmap' in params
    assert params['stability_class'] in ['A', 'B', 'C', 'D', 'E', 'F']
