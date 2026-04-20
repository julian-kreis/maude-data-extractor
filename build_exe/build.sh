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
# 4. Build from Staging
# =====================================
echo "====================================="
echo "Running PyInstaller"
echo "====================================="

cd "$STAGE"

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS detected: Building .app bundle (--windowed)..."
    pyinstaller --clean --noconfirm --onedir --windowed \
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
else
    echo "Linux/Other detected: Building standard directory..."
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
fi

# =====================================
# 5. Move Build to Project Root
# =====================================
echo "Moving build to project root..."
cd ..

rm -rf dist
mkdir dist

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS: copying ONLY .app bundle"
    cp -R "$STAGE/dist/MaudeDataExtractor.app" dist/
else
    echo "Linux/Other: copying full PyInstaller output"
    cp -R "$STAGE/dist/"* dist/
fi

# =====================================
# 6. macOS Ad-hoc Signing
# =====================================
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "====================================="
    echo "Performing ad-hoc signing..."
    echo "====================================="

    APP_BUNDLE="dist/MaudeDataExtractor.app"

    # Remove quarantine and other extended attributes
    echo "Removing extended attributes..."
    xattr -cr "$APP_BUNDLE"

    # Sign the entire bundle recursively with ad-hoc signature
    echo "Signing bundle recursively (ad-hoc)..."
    codesign --force --deep --sign - "$APP_BUNDLE"

    echo "Ad-hoc signing completed"
fi

echo "====================================="
echo "BUILD COMPLETE"

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Final build is in: ./dist/MaudeDataExtractor.app"
else
    echo "Final build is in: ./dist/MaudeDataExtractor/"
fi

echo "====================================="