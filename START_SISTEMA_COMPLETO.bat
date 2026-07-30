@echo off
echo ================================================================
echo    ROBOT TRADER 2026 - AVVIO SISTEMA COMPLETO
echo ================================================================
echo.

cd /d "%~dp0PYTHON_SCRIPTS"

echo [1/3] Avvio Backend Dashboard...
start "Backend" cmd /k python dashboard_backend.py
timeout /t 3 >nul

cd /d "%~dp0"

echo [2/3] Avvio Server Web...
start "WebServer" cmd /k python -m http.server 8080
timeout /t 3 >nul

echo [3/3] Apertura Dashboard...
timeout /t 2 >nul
start http://localhost:8080/dashboard_DINAMICA.html

echo.
echo ================================================================
echo SISTEMA AVVIATO!
echo ================================================================
echo.
echo Dashboard: http://localhost:8080/dashboard_DINAMICA.html
echo Username: admin
echo Password: RobotTrader2026!
echo.
echo NON CHIUDERE le 2 finestre CMD!
echo ================================================================
echo.
pause
