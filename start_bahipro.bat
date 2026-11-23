@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto no_python

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto old_python

python -c "import flask, pandas, matplotlib" >nul 2>nul
if errorlevel 1 (
  echo Installing BahiPro Python dependencies...
  python -m pip install -r requirements.txt
  if errorlevel 1 goto setup_failed
)

python server.py
pause
exit /b 0

:no_python
echo Python 3.10 or later is required. Install Python and enable Add python.exe to PATH.
pause
exit /b 1

:old_python
echo BahiPro needs Python 3.10 or later. Install a current Python version and try again.
pause
exit /b 1

:setup_failed
echo Dependency installation failed. Check your internet connection and try again.
pause
exit /b 1
