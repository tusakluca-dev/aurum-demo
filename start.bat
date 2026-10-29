@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
start "Aurum Browser" http://127.0.0.1:8765
.venv\Scripts\python.exe app.py
pause
exit /b
:failed
echo Installation fehlgeschlagen. Python 3.12 64-bit und Internetverbindung pruefen.
pause
