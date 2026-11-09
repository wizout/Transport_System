@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d %~dp0
if not exist results mkdir results

python -m pip install -q -r requirements.txt 2>nul

call :start_redis
echo ===== Redis =====
python redis_demo.py > results\redis_demo.txt
type results\redis_demo.txt

echo.
echo ===== SQL vs MongoDB =====
python bench.py %*

echo.
pause
exit /b

:start_redis
set REDIS=
for /r "%~dp0redis" %%f in (redis-server.exe) do if exist "%%f" set REDIS=%%f
if defined REDIS start "redis" /min "%REDIS%"
if defined REDIS timeout /t 2 >nul
exit /b
