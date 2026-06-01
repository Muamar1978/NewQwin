import numpy as np
import pandas as pd
from forecast_model import AirQualityForecastModel
from datetime import datetime, timedelta

def verify_forecast_model():
    print("Verifying Forecast Model Fixes...")
    
    # Check dynamic year
    model = AirQualityForecastModel(sequence_length=12, forecast_horizon=6)
    current_year = datetime.now().year
    
    # Create dummy data
    dates = pd.date_range(start=f'{current_year}-01-01', periods=24, freq='h')
    df = pd.DataFrame({
        'timestamp': dates,
        'Concentration': np.random.rand(24) * 100,
        'X (m)': 1000,
        'Y (m)': 2000
    })
    
    # Try to prepare features
    print("Testing feature preparation with current year...")
    try:
        prep_df = model._prepare_single_pollutant_features(df, None)
        print(f"Success! Prepared {len(prep_df)} records.")
        # Check if year is current
        if prep_df.index[0].year == current_year:
            print("Year check: OK")
        else:
            print(f"Year check: FAILED ( {prep_df.index[0].year} != {current_year} )")
    except Exception as e:
        print(f"Feature prep failed: {e}")

    # Mock prediction to test reshape fix
    # Since we can't easily train without TF in this scratch script without full env, 
    # we'll mock the model part but test the predict method logic.
    print("\nTesting predict reshape logic...")
    model.is_trained = True
    model.forecast_horizon = 6
    model.pollutants = ['Concentration']
    model.feature_scaler = type('obj', (object,), {'transform': lambda self, x: x})()
    model.target_scaler = type('obj', (object,), {'inverse_transform': lambda self, x: x})()
    
    # Create a mock TF model that returns (1, self.forecast_horizon * 1)
    class MockModel:
        def predict(self, X, verbose=0):
            return np.zeros((1, 6 * 1))
    
    model.model = MockModel()
    
    # Case 1: hours = forecast_horizon (default)
    print("Scenario: Predicting for trained horizon (6 hours)")
    try:
        res = model.predict(np.zeros((12, 1)), hours=6)
        print(f"Reshape check: OK. Result shape: {res.shape}")
    except Exception as e:
        print(f"Predict (6) failed: {e}")
        
    # Case 2: hours < forecast_horizon
    print("Scenario: Predicting for less than trained horizon (3 hours)")
    try:
        res = model.predict(np.zeros((12, 1)), hours=3)
        print(f"Reshape check: OK. Result shape: {res.shape}")
        if res.shape[0] == 3:
            print("Clipping check: OK")
    except Exception as e:
        print(f"Predict (3) failed: {e}")

    # Case 3: hours > forecast_horizon (should return horizon)
    print("Scenario: Predicting for more than trained horizon (12 hours)")
    try:
        # Note: In my fix, I return the horizon even if more is asked
        res = model.predict(np.zeros((12, 1)), hours=12)
        print(f"Reshape check: OK. Result shape: {res.shape}")
    except Exception as e:
        print(f"Predict (12) failed: {e}")

if __name__ == "__main__":
    verify_forecast_model()
