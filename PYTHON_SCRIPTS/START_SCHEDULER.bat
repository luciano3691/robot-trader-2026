@echo off
REM ================================================================
REM  ROBOT TRADER 2026 — SCHEDULER DAEMON (restart automatico)
REM  Tieni aperta questa finestra: se lo scheduler crasha, riparte.
REM ================================================================

setlocal

set BASE=C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS
set PYTHON=C:\Users\lucia\AppData\Local\Programs\Python\Python314\python.exe

cd /d "%BASE%"

:loop
echo.
echo [%date% %time%] === AVVIO scheduler_daemon.py ===
%PYTHON% scheduler_daemon.py
echo.
echo [%date% %time%] Scheduler terminato (exit=%errorlevel%). Riavvio tra 30 sec...
timeout /t 30 /nobreak > nul
goto loop
