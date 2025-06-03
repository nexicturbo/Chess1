@echo off
cd /d "%~dp0"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing dependencies...
    venv\Scripts\pip.exe install -r requirements.txt
)

venv\Scripts\python.exe src\gui.py
pause
