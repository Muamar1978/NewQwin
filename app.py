from flask import Flask, render_template
from flask_cors import CORS
from flask_caching import Cache
from config import Config
from routes.data import data_bp
from routes.simulation import sim_bp
from routes.forecast import forecast_bp
from routes.export import export_bp
from state import init_cache
import os

app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

# Initialize Flask-Caching for thread-safe state management
cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': os.path.join(Config.DATA_DIR, 'cache'),
    'CACHE_DEFAULT_TIMEOUT': 3600
})

# Initialize the shared cache object in state module
init_cache(app)

# Register Blueprints
app.register_blueprint(data_bp)
app.register_blueprint(sim_bp)
app.register_blueprint(forecast_bp)
app.register_blueprint(export_bp)

# Ensure directories exist
for directory in [Config.OUTPUT_DIR, Config.UPLOAD_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Data initialization is now manual - users will upload data via the web interface
# Removed automatic initialization to allow user-controlled data management

@app.errorhandler(413)
def request_entity_too_large(error):
    return {"error": "File too large. Maximum allowed size is 500MB."}, 413

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    print("Air Quality Dispersion Model - Modularized Version")
    app.run(debug=True, port=5000)
