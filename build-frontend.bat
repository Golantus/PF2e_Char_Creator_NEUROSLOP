@echo off
chcp 65001 >nul
cd /d "%~dp0frontend"
call npm ci --no-audit --no-fund
if errorlevel 1 goto failed
call npm run build
if errorlevel 1 goto failed
exit /b 0
:failed
pause
exit /b 1
