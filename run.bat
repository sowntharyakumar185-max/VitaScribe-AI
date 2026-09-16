@echo off
cd /d "%~dp0"
echo Installing dependencies (first run may take a few minutes)...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo pip failed. Try: python -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo.
echo Starting server. Open: http://127.0.0.1:5000
echo Press Ctrl+C to stop.
echo.
py app.py
pause
