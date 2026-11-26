@echo off
setlocal EnableExtensions
title CFND - Community-Guided Fake News Detection
cd /d "%~dp0"

rem ---------------------------------------------------------------------
rem  start.bat - one-click launcher for CFND on Windows.
rem
rem  First run : creates a virtual environment (venv) and installs the
rem              packages from requirements.txt.
rem  Later runs: skips the install unless requirements.txt has changed,
rem              so the app also starts without an internet connection.
rem
rem  Stop the server with Ctrl+C. Demo data: run  python seed.py  once
rem  (see README); the bundled cfnd.db already contains some.
rem ---------------------------------------------------------------------

set "PORT=5000"
set "URL=http://127.0.0.1:%PORT%"
set "VENV_PY=venv\Scripts\python.exe"

rem --- 1. Find a working Python 3 (py launcher first, then python) ------
set "PY="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python 3 was not found.
    echo Install Python 3.11 from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" in the installer.
    goto :fail
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 (
    echo CFND needs Python 3.8 or newer ^(3.11 recommended^).
    goto :fail
)

rem --- 2. Create the virtual environment on the first run ---------------
if not exist "%VENV_PY%" (
    echo Creating the virtual environment - first run only...
    %PY% -m venv venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        goto :fail
    )
)

rem --- 3. Install packages only when requirements.txt changed -----------
fc /b requirements.txt "venv\requirements.installed" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Installing the dependencies failed. Check your internet
        echo connection and run start.bat again.
        goto :fail
    )
    copy /y requirements.txt "venv\requirements.installed" >nul
)

rem --- 4. Make sure the port is free -------------------------------------
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo Port %PORT% is already in use - CFND may already be running.
    echo Open %URL% in your browser, or close the other program and try again.
    goto :fail
)

rem --- 5. Start the server and open the browser once it is up -----------
echo.
echo Starting CFND at %URL%
echo Press Ctrl+C in this window to stop the server.
echo.
start "" /min cmd /c "ping -n 4 127.0.0.1 >nul & start %URL%"
"%VENV_PY%" run.py
set "CODE=%errorlevel%"

echo.
if not "%CODE%"=="0" (
    echo CFND stopped with exit code %CODE%. If you did not press Ctrl+C,
    echo read the error message above.
    pause
)
exit /b %CODE%

:fail
echo.
pause
exit /b 1
