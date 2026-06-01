#!/bin/bash
echo "======================================================"
echo "Air Quality Dispersion Model - Setup (Linux/macOS)"
echo "======================================================"

# Check for Python
if ! command -v python3 &> /dev/null
then
    echo "[ERROR] python3 could not be found. Please install it."
    exit 1
fi

# Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate Environment
source .venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "======================================================"
echo "Setup complete!"
echo "To run the app: source .venv/bin/activate && python3 app.py"
echo "======================================================"
