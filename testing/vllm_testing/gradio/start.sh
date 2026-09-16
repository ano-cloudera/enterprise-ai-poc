#!/bin/bash
set -e

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Starting application..."
python app.py