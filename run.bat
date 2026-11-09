@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d %~dp0

python -m pip install -q -r requirements.txt
python src\setup_db.py
if errorlevel 1 goto end
echo.
python src\main.py
:end
echo.
pause
