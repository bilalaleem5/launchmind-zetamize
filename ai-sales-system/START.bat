@echo off
title ZetaMize AI Sales System
color 0a
echo.
echo  ===============================================
echo    ZetaMize AI Sales System ^| Starting...
echo  ===============================================
echo.
cd /d "%~dp0"
echo  [1/3] Checking Python...
python --version
echo.
echo  [2/3] Initializing database...
python -c "import sys; sys.path.insert(0,'%~dp0'); from database import init_db; init_db()"
echo.
echo  [3/3] Starting Dashboard...
echo.
echo  -----------------------------------------------
echo    OPEN YOUR BROWSER: http://localhost:5000
echo  -----------------------------------------------
echo.
start "" "http://localhost:5000"
python dashboard\app.py
pause
