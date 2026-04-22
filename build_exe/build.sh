#!/bin/bash

set -e
cd ..

echo "====================================="
echo "MaudeDataExtractor CLEAN BUILD"
echo "====================================="

STAGE="build_stage"

# =====================================
# 1. Clean and Create Staging Area
# =====================================
rm -rf "$STAGE"
mkdir "$STAGE"

echo "Creating staging folder..."

# Define folders to exclude
EXCLUDES=(
  venv
  .git
  __pycache__
  build
  dist
  data_csv
  data_json
  data_excel
  analysis_excel
  analysis_json
  "$STAGE"
)

# Build rsync exclude args
RSYNC_EXCLUDES=""
for item in "${EXCLUDES[@]}"; do
  RSYNC_EXCLUDES+=" --exclude=$item"
done

echo "Copying project safely..."
rsync -av . "$STAGE/" \
  $RSYNC_EXCLUDES \
  --exclude="*.pyc" \
  --exclude="*.pyo" \
  --exclude="*.log" \
  --exclude="*.spec"

# =====================================
# 2. Environment Setup
# =====================================
echo "====================================="
echo "Setting up venv"
echo "====================================="

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install --upgrade pyinstaller

# =====================================
# 3. Clean Old Build Artifacts
# =====================================
rm -rf build dist *.spec

# =====================================
# 4. Build EXE from Staging
# =====================================
echo "====================================="
echo "Running PyInstaller"
echo "====================================="

cd "$STAGE"

# Note: Added --add-data ".:." and --collect-binaries ctypes
# On Linux/macOS, PyInstaller uses : as a separator for --add-data
pyinstaller --clean --noconfirm --onedir \
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

# Move the final product back to the main project root
echo "Moving build to project root..."
cd ..
rm -rf dist
cp -R "$STAGE/dist" ./dist

echo "====================================="
echo "BUILD COMPLETE"
echo "Final build is in: ./dist/MaudeDataExtractor/"
echo "====================================="
