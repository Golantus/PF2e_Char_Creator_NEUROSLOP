@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto check_dependencies
call setup.bat
if errorlevel 1 exit /b 1
:check_dependencies
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,httpx,bs4,lxml,bleach,socksio" >nul 2>&1
if not errorlevel 1 goto run
call setup.bat
if errorlevel 1 exit /b 1
:run
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 pause
