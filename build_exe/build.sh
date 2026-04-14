#!/bin/bash

cd ..

set -e

echo "====================================="
echo "Building MaudeDataExtractor"
echo "OS: $(uname -s)"
echo "====================================="

# Create and activate venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install --upgrade pyinstaller

# Clean old builds
rm -rf build dist *.spec

echo "====================================="
echo "Running PyInstaller build"
echo "====================================="

pyinstaller \
--clean --noconfirm --onedir \
--name "MaudeDataExtractor" \
--copy-metadata streamlit \
--collect-all streamlit \
--collect-all dotenv \
--collect-all dedupe \
--collect-all pandas \
--collect-all sklearn \
--collect-all plotly \
--collect-binaries ctypes \
--collect-binaries numpy \
--add-data ".:." \
launcher.py

echo "====================================="
echo "BUILD COMPLETE"
echo "Output: dist/MaudeDataExtractor/"
echo "====================================="