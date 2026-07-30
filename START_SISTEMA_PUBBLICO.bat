@echo off
chcp 65001 >nul
echo.
echo ================================================================
echo   ROBOT TRADER 2026 - AVVIO SISTEMA PUBBLICO
echo ================================================================
echo.

set SCRIPTS=%~dp0PYTHON_SCRIPTS
set NGROKDIR=%~dp0NGROK

:: Legge dominio statico ngrok
if exist "%NGROKDIR%\ngrok_domain.txt" (
    set /p NGROK_DOMAIN=<"%NGROKDIR%\ngrok_domain.txt"
) else (
    echo ERRORE: %NGROKDIR%\ngrok_domain.txt non trovato.
    echo Crea il file con il tuo dominio statico ngrok (es: mio-nome.ngrok-free.app)
    echo Poi riesegui questo script.
    pause
    exit /b 1
)

:: Controlla ngrok.exe
if not exist "%NGROKDIR%\ngrok.exe" (
    echo ERRORE: ngrok.exe non trovato in NGROK\
    echo Scaricalo da https://ngrok.com/download e mettilo in: %NGROKDIR%
    pause
    exit /b 1
)

echo [1/3] Avvio Dashboard (porta 8080)...
start "Robot Trader - Dashboard" cmd /k "cd /d "%SCRIPTS%" && python dashboard.py"
timeout /t 4 >nul

echo [2/3] Avvio Scheduler (screener 23:00 + social 08:00)...
start "Robot Trader - Scheduler" cmd /k "cd /d "%SCRIPTS%" && python scheduler_daemon.py"
timeout /t 2 >nul

echo [3/3] Avvio Tunnel ngrok...
start "Robot Trader - Tunnel HTTPS" cmd /k ""%NGROKDIR%\ngrok.exe" http --domain=%NGROK_DOMAIN% 8080"
timeout /t 3 >nul

echo.
echo ================================================================
echo SISTEMA AVVIATO
echo.
echo  Locale:   http://localhost:8080
echo  Pubblico: https://%NGROK_DOMAIN%
echo.
echo NON chiudere le 3 finestre CMD!
echo ================================================================
echo.
start https://%NGROK_DOMAIN%
pause
