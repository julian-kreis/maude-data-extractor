@echo off
setlocal
cd ..

echo =====================================
echo MaudeDataExtractor CLEAN AUTO-BUILD
echo =====================================

set STAGE=build_stage

REM =====================================
REM 1. Clean and Create Staging Area
REM =====================================
if exist %STAGE% rmdir /s /q %STAGE%
mkdir %STAGE%

echo Preparing clean source files...

REM Define folders to exclude
set EXCLUDES=venv .git __pycache__ build dist data_csv data_json data_excel analysis_excel analysis_json %STAGE%

REM Copy project safely to staging (Excluding the junk)
robocopy . %STAGE% /E /XD %EXCLUDES% /XF *.pyc *.pyo *.log *.spec

REM =====================================
REM 2. Environment Setup
REM =====================================
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo Upgrading dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install --upgrade pyinstaller

REM =====================================
REM 3. Clean Old Build Artifacts
REM =====================================
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM =====================================
REM 4. Build EXE from Staging
REM =====================================
echo.
echo Building executable from clean stage...

:: We move into staging so PyInstaller sees this as the 'root'
cd %STAGE%

pyinstaller --clean --noconfirm --onedir --windowed ^
--name "MaudeDataExtractor" ^
--copy-metadata streamlit ^
--collect-all streamlit ^
--collect-all dotenv ^
--collect-all dedupe ^
--collect-all pandas ^
--collect-all sklearn ^
--collect-all plotly ^
--collect-binaries ctypes ^
--collect-binaries numpy ^
--add-data ".;." ^
launcher.py

REM Move the final product back to the main project root and cleanup
echo Moving build to project root...
cd ..
if exist dist_final rmdir /s /q dist_final
xcopy "%STAGE%\dist" ".\dist" /E /I /Y

echo =====================================
echo BUILD COMPLETE
echo Final EXE is in: .\dist\MaudeDataExtractor\
echo =====================================

pause
endlocal