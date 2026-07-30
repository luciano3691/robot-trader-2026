@echo off
cd /d "%~dp0PYTHON_SCRIPTS"
start "Backend" cmd /k python dashboard_backend.py
timeout /t 3 >nul
cd /d "%~dp0"
start "WebServer" cmd /k python -m http.server 8080
timeout /t 2 >nul
start http://localhost:8080/dashboard_DINAMICA.html
