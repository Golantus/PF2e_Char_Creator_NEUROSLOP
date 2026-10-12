@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto tests
call setup.bat
if errorlevel 1 exit /b 1
:tests
".venv\Scripts\python.exe" -m pip install -r backend\requirements-dev.txt
if errorlevel 1 exit /b 1
cd backend
"..\.venv\Scripts\python.exe" -m pytest -q
pause
