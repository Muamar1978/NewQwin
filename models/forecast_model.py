import numpy as np
import pandas as pd
# from sklearn.preprocessing import MinMaxScaler
import os
import json
from datetime import datetime, timedelta

# Suppress matplotlib 3D warning
import warnings
warnings.filterwarnings("ignore", module="matplotlib")

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Import Config at the module level for path resolution
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# Check TensorFlow availability at module level
try:
    import tensorflow as tf
    from tensorflow.keras import layers as keras_layers
    from tensorflow.keras.layers import LayerNormalization, Add, Dropout, Flatten, Dense, LSTM, MultiHeadAttention, Input
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.models import Model
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    tf = None
    keras_layers = None
    LayerNormalization = None
    Add = None
    Dropout = None
    Flatten = None
    Dense = None
    LSTM = None
    MultiHeadAttention = None
    Input = None
    Adam = None
    EarlyStopping = None
    Model = None

# Top-level tensorflow imports disabled to prevent hanging on some systems
class MockLayer:
    def __init__(self, *args, **kwargs): pass

if TF_AVAILABLE:
    TF_BASE_LAYER = tf.keras.layers.Layer
else:
    TF_BASE_LAYER = MockLayer
    layers = type('Mock', (), {'Dense': MockLayer})

if TF_AVAILABLE:
    class GRN(tf.keras.layers.Layer):
        """Gated Residual Network used in TFT to provide non-linear processing"""
        def __init__(self, units, **kwargs):
            super().__init__(**kwargs)
            self.dense1 = keras_layers.Dense(units, activation='elu')
            self.dense2 = keras_layers.Dense(units, activation='elu')
            self.gate = keras_layers.Dense(units, activation='sigmoid')
            self.norm = LayerNormalization()
            self.res = keras_layers.Dense(units)

        def call(self, inputs):
            x = self.dense1(inputs)
            x = self.dense2(x)
            g = self.gate(inputs)
            # Element-wise multiplication (gating)
            out = x * g
            # Residual connection + Normalization
            return self.norm(Add()([out, self.res(inputs)]))

    class VSN(tf.keras.layers.Layer):
        """Variable Selection Network to weight the importance of different input features"""
        def __init__(self, num_inputs, units, **kwargs):
            super().__init__(**kwargs)
            self.num_inputs = num_inputs
            self.grns = [GRN(units) for _ in range(num_inputs)]
            self.weights_dense = keras_layers.Dense(num_inputs, activation='softmax')

        def call(self, inputs):
            # inputs shape: (batch, seq_len, num_inputs)
            processed = []
            for i in range(self.num_inputs):
                # Process each feature through its own GRN
                feat = inputs[:, :, i:i+1]
                processed.append(self.grns[i](feat))
            
            # Stack processed features: (batch, seq_len, num_inputs, units)
            processed = tf.stack(processed, axis=2)
            
            # Calculate weights for each feature: (batch, seq_len, num_inputs)
            # We use a simple pooling of the input to decide weights
            weights = self.weights_dense(tf.reduce_mean(inputs, axis=1)) # (batch, num_inputs)
            weights = tf.expand_dims(tf.expand_dims(weights, 1), -1) # (batch, 1, num_inputs, 1)
            
            # Weighted sum of processed features
            weighted = processed * weights
            return tf.reduce_sum(weighted, axis=2) # (batch, seq_len, units)
else:
    GRN = MockLayer
    VSN = MockLayer

class AirQualityForecastModel:
    def __init__(self, sequence_length=24, forecast_horizon=24):
        self.sequence_length = sequence_length
        self.forecast_horizon = forecast_horizon
        self.pollutants = ['CO', 'NOx', 'PM10', 'PM2.5']
        self.feature_scaler = None
        self.target_scaler = None
        self.model = None
        self.is_trained = False
        self.weather_cols = ['TEMP_C', 'WS', 'WD']
        self.time_cols = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos', 'month_sin', 'month_cos']
        self.history = None
        
    def _create_time_features(self, df):
        df = df.copy()
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'], errors='coerce')
            df['hour'], df['day'], df['month'] = ts.dt.hour, ts.dt.dayofweek, ts.dt.month
            
            # If HOUR, DAY, MONTH columns exist, prioritize them or fill missing from timestamp
            # Use a fixed leap year (2024) to ensure consistent day-of-week and leap-year math
            reference_year = 2024
            if all(col in df.columns for col in ['HOUR', 'DAY', 'MONTH']):
                # Try to infer year from data if available, otherwise use reference year
                if 'YEAR' in df.columns:
                    year_val = df['YEAR'].iloc[0] if len(df) > 0 else reference_year
                else:
                    year_val = reference_year
                df['timestamp'] = pd.to_datetime(f'{year_val}-' + df['MONTH'].astype(str) + '-' + df['DAY'].astype(str) + ' ' + df['HOUR'].astype(str) + ':00:00', errors='coerce')
                df['hour'], df['day'], df['month'] = df['HOUR'], df['DAY'] - 1, df['MONTH']
            else:
                # Handle cases where ts might have failed to parse
                df['hour'] = df['hour'].fillna(12)
                df['day'] = df['day'].fillna(0)
                df['month'] = df['month'].fillna(1)
        else:
            df['hour'], df['day'], df['month'] = 12, 0, 1
        
        df['hour_sin'], df['hour_cos'] = np.sin(2 * np.pi * df['hour'] / 24), np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'], df['day_cos'] = np.sin(2 * np.pi * df['day'] / 7), np.cos(2 * np.pi * df['day'] / 7)
        df['month_sin'], df['month_cos'] = np.sin(2 * np.pi * df['month'] / 12), np.cos(2 * np.pi * df['month'] / 12)
        return df
    
    def _prepare_single_pollutant_features(self, pollution_df, weather_df):
        if 'timestamp' not in pollution_df.columns: raise ValueError("timestamp column is required")
        
        # Fuzzy match for concentration column
        conc_col = None
        # Preferred order: exact match, starts with, contains
        pollutant_keys = ['co', 'nox', 'pm10', 'pm2.5', 'pm25', 'concentration']
        for key in pollutant_keys:
            for col in pollution_df.columns:
                if key == col.lower():
                    conc_col = col
                    break
            if conc_col: break
        
        if conc_col is None:
            for col in pollution_df.columns:
                if any(key in col.lower() for key in pollutant_keys):
                    conc_col = col
                    break
        
        if conc_col is None: raise ValueError("No concentration column found (could not find any column containing 'concentration' or matching pollutant names)")
        
        self.pollutants = [conc_col]
        df_copy = pollution_df.copy()
        df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
        df_copy = df_copy.dropna(subset=['timestamp']).sort_values('timestamp')
        df_copy = df_copy[df_copy[conc_col] > 0]
        
        if len(df_copy) < 24: raise ValueError("Not enough valid data. Need at least 24 records.")
        
        # Aggregate by timestamp to avoid duplicate index labels.
        # Multiple spatial points at the same timestamp are averaged into one row.
        numeric_cols = df_copy.select_dtypes(include=[np.number]).columns.tolist()
        location_features = df_copy.groupby('timestamp')[numeric_cols].mean()
        location_features = location_features.ffill().bfill()
        
        if weather_df is not None:
            weather_agg = weather_df.copy()
            # Use a fixed leap year (2024) to ensure consistent day-of-week and leap-year math
            reference_year = 2024
            if 'HOUR' in weather_agg.columns and 'DAY' in weather_agg.columns and 'MONTH' in weather_agg.columns:
                # Try to infer year from data if available, otherwise use reference year
                if 'YEAR' in weather_agg.columns:
                    year_val = weather_agg['YEAR'].iloc[0] if len(weather_agg) > 0 else reference_year
                else:
                    year_val = reference_year
                weather_agg['timestamp'] = pd.to_datetime(f'{year_val}-' + weather_agg['MONTH'].astype(str) + '-' + weather_agg['DAY'].astype(str) + ' ' + weather_agg['HOUR'].astype(str) + ':00:00', errors='coerce')
                weather_agg = weather_agg.set_index('timestamp')
            elif 'timestamp' not in weather_agg.columns:
                weather_agg['timestamp'] = pd.date_range(start=f'{reference_year}-01-01', periods=len(weather_agg), freq='h')
                weather_agg = weather_agg.set_index('timestamp')
            
            # Remove any duplicate timestamps in weather data as well
            weather_agg = weather_agg[~weather_agg.index.duplicated(keep='first')]
            
            weather_cols = [c for c in self.weather_cols if c in weather_agg.columns]
            weather_reindexed = weather_agg[weather_cols].reindex(location_features.index, method='ffill').bfill().fillna(0)
            for col in weather_cols: location_features[col] = weather_reindexed[col].values
        else:
            for col in self.weather_cols: location_features[col] = 20
        
        location_features = self._create_time_features(location_features)
        feature_cols = self.pollutants + self.weather_cols + self.time_cols
        if 'X (m)' in location_features.columns: feature_cols += ['X (m)', 'Y (m)']
        if 'Longitude' in location_features.columns: feature_cols += ['Longitude', 'Latitude']
        
        return location_features[[c for c in feature_cols if c in location_features.columns]]

    def _prepare_features(self, pollution_df, weather_df):
        if 'timestamp' in pollution_df.columns:
            pollution_df = pollution_df.set_index(pd.to_datetime(pollution_df['timestamp']))
        
        weather_agg = pd.DataFrame()
        if weather_df is not None:
            weather_agg = weather_df.copy()
            # Use a fixed leap year (2024) to ensure consistent day-of-week and leap-year math
            reference_year = 2024
            if 'HOUR' in weather_agg.columns and 'DAY' in weather_agg.columns and 'MONTH' in weather_agg.columns:
                # Try to infer year from data if available, otherwise use reference year
                if 'YEAR' in weather_agg.columns:
                    year_val = weather_agg['YEAR'].iloc[0] if len(weather_agg) > 0 else reference_year
                else:
                    year_val = reference_year
                weather_agg['timestamp'] = pd.to_datetime(f'{year_val}-' + weather_agg['MONTH'].astype(str) + '-' + weather_agg['DAY'].astype(str) + ' ' + weather_agg['HOUR'].astype(str) + ':00:00', errors='coerce')
                weather_agg = weather_agg.set_index('timestamp')
            elif 'timestamp' not in weather_agg.columns:
                weather_agg['timestamp'] = pd.date_range(start=f'{reference_year}-01-01', periods=len(weather_agg), freq='h')
                weather_agg = weather_agg.set_index('timestamp')
            weather_agg = weather_agg.resample('h').mean().ffill()
            weather_agg = weather_agg[~weather_agg.index.duplicated(keep='first')]

        if pollution_df.index.name is not None:
            pollution_df = pollution_df[~pollution_df.index.duplicated(keep='first')]
            merged = pollution_df.join(weather_agg, how='inner')
        else:
            # Use a fixed leap year (2024) to ensure consistent day-of-week and leap-year math
            reference_year = 2024
            pollution_df_indexed = pollution_df.copy()
            pollution_df_indexed['timestamp'] = pd.date_range(start=f'{reference_year}-01-01', periods=len(pollution_df_indexed), freq='h')
            pollution_df_indexed = pollution_df_indexed.set_index('timestamp')
            pollution_df_indexed = pollution_df_indexed[~pollution_df_indexed.index.duplicated(keep='first')]
            merged = pollution_df_indexed.join(weather_agg, how='inner')
        
        merged = self._create_time_features(merged.ffill().bfill())
        feature_cols = [c for c in (self.pollutants + self.weather_cols + self.time_cols) if c in merged.columns]
        return merged[feature_cols]

    def _create_sequences(self, data):
        X, y = [], []
        for i in range(len(data) - self.sequence_length - self.forecast_horizon + 1):
            X.append(data[i:i + self.sequence_length])
            y.append(data[i + self.sequence_length:i + self.sequence_length + self.forecast_horizon, :len(self.pollutants)])
        return np.array(X), np.array(y)

    def _build_tft_model(self, n_features):
        """Builds a simplified Temporal Fusion Transformer architecture"""
        import tensorflow as tf
        from tensorflow.keras import layers, models
        from tensorflow.keras.layers import LSTM, Dense, Dropout, MultiHeadAttention, LayerNormalization, Add, Input
        from tensorflow.keras.optimizers import Adam
        
        inputs = Input(shape=(self.sequence_length, n_features))
        
        # 1. Variable Selection Network (VSN)
        # Weights each input feature's importance
        x = VSN(n_features, 32)(inputs) # (batch, seq, 32)
        
        # 2. Temporal Processing (LSTM Encoder)
        # Captures sequence dependencies
        lstm_out = LSTM(64, return_sequences=True)(x)
        
        # 3. Multi-Head Attention (The 'Transformer' part)
        # Captures long-range patterns across the sequence
        attn_out = MultiHeadAttention(num_heads=4, key_dim=64)(lstm_out, lstm_out)
        attn_out = LayerNormalization()(Add()([attn_out, lstm_out]))
        
        # 4. Gated Residual Network (GRN)
        # Non-linear processing of the temporal features
        grn_out = GRN(64)(attn_out)
        
        # 5. Forecasting Head
        # Flatten sequence and predict horizon
        flat = layers.Flatten()(grn_out)
        dense1 = Dense(64, activation='relu')(flat)
        dropout = Dropout(0.2)(dense1)
        output = Dense(self.forecast_horizon * len(self.pollutants), activation='linear')(dropout)
        
        model = models.Model(inputs=inputs, outputs=output)
        model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
        return model

    def train(self, pollution_df, weather_df, epochs=50, batch_size=32, validation_split=0.2):
        if not TF_AVAILABLE: raise ImportError("TensorFlow is not available")
        
        # Update new_format check to be fuzzy
        has_conc = any('concentration' in c.lower() for c in pollution_df.columns)
        has_pollutant = any(p in pollution_df.columns for p in ['CO', 'NOx', 'PM10', 'PM2.5'])
        new_format = (has_conc or has_pollutant) and 'timestamp' in pollution_df.columns
        data = self._prepare_single_pollutant_features(pollution_df, weather_df) if new_format else self._prepare_features(pollution_df, weather_df)
        
        available_pollutants = [p for p in self.pollutants if p in data.columns]
        if not available_pollutants: raise ValueError("No valid pollutants found")
        self.pollutants = available_pollutants
        
        feature_cols = self.pollutants + self.weather_cols + self.time_cols
        if 'X (m)' in data.columns: feature_cols += ['X (m)', 'Y (m)']
        if 'Longitude' in data.columns: feature_cols += ['Longitude', 'Latitude']
        feature_cols = [c for c in feature_cols if c in data.columns]
        
        self.feature_columns = feature_cols
        data = data[feature_cols].fillna(0)
        
        from sklearn.preprocessing import MinMaxScaler
        self.feature_scaler, self.target_scaler = MinMaxScaler(), MinMaxScaler()
        target_data = data[self.pollutants].values
        self.target_scaler.fit(target_data)
        
        scaled_data = self.feature_scaler.fit_transform(data.values)
        X, y = self._create_sequences(scaled_data)
        
        if len(X) < 2: raise ValueError(f"Insufficient data for training. Generated {len(X)} sequences from {len(data)} total records. Please upload a dataset with more timestamps or reduce the sequence length / forecast horizon.")
        
        # Align targets for the forecast horizon
        target_indices = [feature_cols.index(p) for p in self.pollutants]
        y_targets = np.zeros((y.shape[0], y.shape[1], len(self.pollutants)))
        for t in range(y.shape[1]):
            for i, idx in enumerate(target_indices):
                y_targets[:, t, i] = y[:, t, idx]
        y = y_targets.reshape(y.shape[0], y.shape[1] * len(self.pollutants))
        
        val_size = int(len(X) * validation_split)
        X_train, X_val = X[:-val_size], X[-val_size:]
        y_train, y_val = y[:-val_size], y[-val_size:]
        
        self.model = self._build_tft_model(X.shape[2])
        
        from tensorflow.keras.callbacks import EarlyStopping
        early_stop = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        self.history = self.model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, validation_data=(X_val, y_val), callbacks=[early_stop], verbose=0)
        
        val_pred = self.model.predict(X_val, verbose=0)
        val_mse = np.mean((y_val - val_pred) ** 2)
        self.is_trained = True
        
        return {'val_mse': float(val_mse), 'val_rmse': float(np.sqrt(val_mse)), 'train_samples': len(X_train), 'val_samples': len(X_val), 'epochs_trained': len(self.history.history['loss'])}

    def predict(self, recent_data, hours=None):
        if not self.is_trained: raise ValueError("Model not trained")
        hours = hours or self.forecast_horizon
        
        if len(recent_data) < self.sequence_length:
            padding = np.zeros((self.sequence_length - len(recent_data), recent_data.shape[1]))
            recent_data = np.vstack([padding, recent_data])
        
        scaled = self.feature_scaler.transform(recent_data)
        X = scaled[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        predictions = self.model.predict(X, verbose=0)
        
        # Always reshape to the horizon the model was trained for
        predictions = predictions.reshape(self.forecast_horizon, len(self.pollutants))
        
        # If specific hours requested (less than horizon), slice it
        if hours and hours < self.forecast_horizon:
            predictions = predictions[:hours]
        # If more requested, we can only return what we have (the horizon)
        
        predictions = self.target_scaler.inverse_transform(predictions)
        return np.maximum(predictions, 0)

    def forecast_from_data(self, pollution_df, weather_df, hours=24):
        # Update new_format check to be fuzzy
        has_conc = any('concentration' in c.lower() for c in pollution_df.columns)
        has_pollutant = any(p in pollution_df.columns for p in ['CO', 'NOx', 'PM10', 'PM2.5'])
        new_format = (has_conc or has_pollutant) and 'timestamp' in pollution_df.columns
        data = self._prepare_single_pollutant_features(pollution_df, weather_df) if new_format else self._prepare_features(pollution_df, weather_df)
        
        feature_cols = [c for c in (self.feature_columns if hasattr(self, 'feature_columns') else self.pollutants + self.weather_cols + self.time_cols) if c in data.columns]
        data = data[feature_cols].fillna(0)
        
        predictions = self.predict(data.values[-self.sequence_length:], hours)
        
        # Clamp hours to available predictions to prevent IndexError
        actual_hours = min(hours, len(predictions))
        
        results = []
        base_time = datetime.now()
        for i in range(actual_hours):
            pred_time = base_time + timedelta(hours=i+1)
            res = {'timestamp': pred_time.strftime('%Y-%m-%d %H:%M:%S'), 'hour': pred_time.hour, 'day': pred_time.day, 'month': pred_time.month}
            for j, p in enumerate(self.pollutants):
                res[p] = float(predictions[i, j]) if j < predictions.shape[1] else 0.0
            results.append(res)
        return results

    def get_model_info(self):
        try:
            import tensorflow as tf
            tf_available = True
        except ImportError:
            tf_available = False
        return {'is_trained': self.is_trained, 'sequence_length': self.sequence_length, 'forecast_horizon': self.forecast_horizon, 'tensorflow_available': tf_available}
