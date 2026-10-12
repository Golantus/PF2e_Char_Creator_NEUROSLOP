@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PF2E_PYTHON=py -3"
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 goto create_venv
set "PF2E_PYTHON=python"
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 goto create_venv
echo Нужен Python 3.10 или новее. Установите его с https://www.python.org/downloads/windows/
echo При установке отметьте Add python.exe to PATH. Затем повторно откройте start.bat.
pause
exit /b 1
:create_venv
if exist ".venv\Scripts\python.exe" goto install
%PF2E_PYTHON% -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto failed
echo Установка завершена.
exit /b 0
:failed
echo Установка не завершена. Проверьте подключение к интернету и сообщение выше.
pause
exit /b 1
