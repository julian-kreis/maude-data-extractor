@echo off
cd ..

setlocal

echo =====================================
echo MaudeDataExtractor AUTO BUILD
echo =====================================

REM =====================================
REM 1. Ensure venv exists
REM =====================================
if not exist venv (
    echo No venv found. Creating virtual environment...
    python -m venv venv
)

REM =====================================
REM 2. Activate venv
REM =====================================
echo Activating virtual environment...
call venv\Scripts\activate

REM =====================================
REM 3. Upgrade pip
REM =====================================
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM =====================================
REM 4. Check/install requirements
REM =====================================
echo.
echo Installing requirements if needed...

REM This installs everything (pip handles "already installed" automatically)
pip install -r requirements.txt

REM =====================================
REM 5. Ensure PyInstaller exists
REM =====================================
echo.
echo Ensuring PyInstaller is installed...
pip install --upgrade pyinstaller

REM =====================================
REM 6. Clean old builds
REM =====================================
echo.
echo Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

REM =====================================
REM 7. Build EXE
REM =====================================
echo.
echo =====================================
echo Building executable...
echo =====================================

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

echo.
echo =====================================
echo BUILD COMPLETE
echo =====================================
echo Output: dist\MaudeDataExtractor\
echo =====================================

pause
endlocal