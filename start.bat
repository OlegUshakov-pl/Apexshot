@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [*] Creating virtual environment .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo [!] Failed to create venv. Check that Python is installed and on PATH.
    pause
    exit /b 1
  )
)

if not exist ".venv\Lib\site-packages\fastapi" (
  echo [*] Installing dependencies from requirements.txt ...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [!] Failed to install dependencies.
    pause
    exit /b 1
  )
)

echo [*] Starting AI-snapshots: http://127.0.0.1:8000
echo [*] Press Ctrl+C to stop
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
pause