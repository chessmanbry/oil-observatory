@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -c "import yaml" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)
echo Open http://localhost:8501 in your browser.
echo Press Ctrl+C to stop the local server.
.venv\Scripts\python.exe serve.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo Startup failed. Please check Python 3.10+ and the README.
pause
exit /b 1
