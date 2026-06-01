# ARCHITECTURE DOCUMENTATION - Air Quality Dispersion Model v008

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Component Description](#component-description)
4. [API Endpoints](#api-endpoints)
5. [Data Flow](#data-flow)
6. [LSTM Forecasting Model](#lstm-forecasting-model)
7. [Frontend Features](#frontend-features)
8. [Configuration](#configuration)

---

## 1. Project Overview

This is a Flask-based web application for Gaussian air pollution dispersion modeling with LSTM-based air quality forecasting. The system processes GIS data from shapefiles, runs atmospheric dispersion simulations, and provides AI-powered predictions.

**Version:** v008
**Last Updated:** 2026-03-17

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Browser)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  GIS Viewer │  │  Dashboard  │  │ LSTM Panel  │               │
│  │  (Leaflet)  │  │  (Charts)   │  │ (Training)  │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
└─────────┼────────────────┼────────────────┼──────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Flask Backend (app.py)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Gaussian   │  │   Upload    │  │   LSTM      │             │
│  │   Model      │  │   Handler   │  │   API       │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼────────────────┼────────────────┼──────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ shapefiles/  │  │   uploads/    │  │   output/     │
│ road data    │  │ historical   │  │ CSV/shapefile│
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## 3. Component Description

### 3.1 Backend Components

| File | Description |
|------|-------------|
| `app.py` | Flask application, API endpoints, session management |
| `gaussian_model.py` | Gaussian plume dispersion model for simulation |
| `forecast_model.py` | LSTM neural network for air quality prediction |
| `start.sh` | Startup script for running server in background |

### 3.2 Frontend Components

| File | Description |
|------|-------------|
| `templates/index.html` | Single-page application with GIS viewer, controls, and AI panel |

### 3.3 Data Directories

| Directory | Description |
|-----------|-------------|
| `uploads/` | Stores uploaded historical pollution CSV files |
| `output/` | Generated CSV and shapefile outputs |
| `static/` | CSS, JavaScript, and assets |

---

## 4. API Endpoints

### 4.1 Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main application page |
| `/api/roads` | GET | Road network GeoJSON |
| `/api/weather` | GET | Weather statistics |
| `/api/simulate` | POST | Run dispersion simulation |
| `/api/shapefile` | POST | Generate shapefile output |
| `/api/pollution-data` | GET | Existing pollution points |
| `/api/study-area` | GET | Study area boundary |

### 4.2 AI/LSTM Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload-historical` | POST | Upload historical pollution CSV |
| `/api/forecast/train` | POST | Train LSTM model |
| `/api/forecast` | GET | Get predictions |
| `/api/forecast/status` | GET | Check model status |
| `/api/export-ai-csv` | POST | Export simulation data for AI |
| `/api/export-forecast-format` | POST | Export forecast data |

---

## 5. Data Flow

### 5.1 Simulation Flow
```
User Input → Road Selection → Weather Data → Gaussian Model → Results → Map Display
```

### 5.2 LSTM Training Flow
```
Upload CSV → Process Data → Detect Pollutant → Train Model → Save Model → Display Status
```

### 5.3 Prediction Flow
```
Load Model → Process Recent Data → LSTM Prediction → Results → Export CSV
```

---

## 6. LSTM Forecasting Model

### 6.1 Overview
The LSTM (Long Short-Term Memory) model predicts air pollution levels based on historical data.

### 6.2 Data Processing Pipeline
When user uploads historical pollution CSV:

1. **Load CSV** from `uploads/historical_pollution.csv`
2. **Extract pollutant name** from "Pollutant" column (e.g., CO, NOx, PM10, PM2.5)
3. **Remove "Pollutant" column** - keep concentration values only
4. **Convert timestamp** to datetime
5. **Sort by timestamp**
6. **Filter data** - keep only rows with concentration > 0
7. **Normalize** numerical columns (Longitude, Latitude, X, Y)
8. **Train LSTM** with processed data

### 6.3 Supported Pollutants
- CO (Carbon Monoxide)
- NOx (Nitrogen Oxides)
- PM10 (Particulate Matter 10μm)
- PM2.5 (Particulate Matter 2.5μm)

### 6.4 Model Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| sequence_length | 12 | Number of time steps for input |
| forecast_horizon | 6 | Number of hours to predict |
| epochs | 10 | Training iterations |
| batch_size | 16 | Training batch size |

### 6.5 Features Used
- Concentration (target variable)
- TEMP_C (temperature)
- WS (wind speed)
- WD (wind direction)
- hour_sin, hour_cos (hour encoding)
- day_sin, day_cos (day encoding)
- month_sin, month_cos (month encoding)
- X (m), Y (m) (UTM coordinates)
- Longitude, Latitude (WGS84 coordinates)

---

## 7. Frontend Features

### 7.1 Main Tabs
- **Map** - GIS viewer with Leaflet
- **Simulation** - Road selection, pollutant type, time period
- **Upload** - Data upload interface
- **AI Forecast** - LSTM training and prediction

### 7.2 AI Panel Features
- **Upload Historical Data** - CSV file upload
- **Train LSTM Model** - Train with configurable parameters
- **Get Predictions** - Generate forecasts
- **Model Status** - Display accuracy metrics
- **Export Predictions** - Download CSV

### 7.3 Model Status Display
The Model Status panel shows:
- Status (Trained/Failed)
- Accuracy (RMSE) - as percentage
- Accuracy (MAE) - as percentage
- Validation MSE
- Epochs trained
- Training Samples
- Validation Samples

---

## 8. Configuration

### 8.1 Server Configuration
```bash
# Run with nohup (recommended)
./start.sh

# Or manually
nohup python3 app.py > server.log 2>&1 &
```

### 8.2 Default Parameters
| Parameter | Value |
|-----------|-------|
| Port | 5000 |
| Max upload size | 16MB |
| Session timeout | 30 min |

### 8.3 CSV Format Requirements

**Historical Pollution Data:**
```
timestamp,Longitude,Latitude,X (m),Y (m),Concentration (mg/m³),Pollutant
2024-12-01 00:00:00,44.390432,35.556811,444755,3934965,0.00009835,CO
```

---

## 9. Recent Updates (v008)

### 9.1 Bug Fixes
- Fixed `/api/weather` returning 500 error → returns 404 with message
- Fixed LSTM training to load from uploaded CSV file
- Fixed prediction to use correct pollutant name from training data
- Fixed CSV export to only include predicted pollutant(s)
- Fixed undefined values in prediction results

### 9.2 New Features
- LSTM model with automatic pollutant detection
- Weather data optional for training
- Raw data processing (no hourly resampling)
- Dynamic pollutant columns in exports
- Accuracy display as percentage

### 9.3 Performance Improvements
- Reduced default epochs: 30 → 10
- Reduced batch size: 32 → 16
- Reduced sequence_length: 24 → 12
- Reduced forecast_horizon: 24 → 6

---

## 10. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "No historical pollution data" | Upload CSV file first |
| "Not enough data" | Need at least 24 valid rows |
| "Model not trained" | Train model before predictions |
| "X features mismatch" | Retrain model with current data |

---

## 11. Dependencies

### Python Packages
- flask
- flask-cors
- geopandas
- pandas
- numpy
- pyproj
- shapely
- scipy
- scikit-image
- scikit-learn
- tensorflow
- keras

---

*Document generated: 2026-03-17*
*Version: v008*
