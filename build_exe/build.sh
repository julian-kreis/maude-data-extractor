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

# =====================================
# 5. macOS Ad-hoc Signing (only on Mac) so only a single warning pops up instead of one for every binary
# =====================================
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Signing all binaries manually..."
    APP_PATH="dist/MaudeDataExtractor"

    # 1. Remove attributes
    xattr -cr "$APP_PATH"

    # 2. Find and sign every library/binary inside the folder first
    find "$APP_PATH" -type f \( -name "*.so" -or -name "*.dylib" -or -name "Python" \) -print0 | xargs -0 codesign --force --sign -

    # 3. Sign the main executable last
    codesign --force --sign - "$APP_PATH/MaudeDataExtractor"

    echo "Manual recursive signing complete"
fi

echo "====================================="
echo "BUILD COMPLETE"
echo "Final build is in: ./dist/MaudeDataExtractor/"
echo "====================================="