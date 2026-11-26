@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -m venv venv
    if errorlevel 1 (
        echo Python was not found. Install Python 3 and try again.
        pause
        exit /b 1
    )
)

echo Installing/updating dependencies...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Starting CFND at http://127.0.0.1:5000
start "" http://127.0.0.1:5000
"venv\Scripts\python.exe" run.py

if errorlevel 1 (
    echo The application stopped unexpectedly.
    pause
)
endlocal
