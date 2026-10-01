@echo off
setlocal
cd /d "%~dp0"

echo [*] Installing AI-snapshots dependencies ...

if not exist ".venv\Scripts\python.exe" (
  echo [*] Creating virtual environment .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo [!] Failed to create venv. Check that Python is installed and on PATH.
    pause
    exit /b 1
  )
)

echo [*] Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [!] Failed to upgrade pip.
  pause
  exit /b 1
)

echo [*] Installing requirements.txt ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [!] Failed to install dependencies.
  pause
  exit /b 1
)

echo.
echo [+] Installation complete.
echo [*] Run start.bat to launch the app: http://127.0.0.1:8000
echo.
pause
exit /b 0
