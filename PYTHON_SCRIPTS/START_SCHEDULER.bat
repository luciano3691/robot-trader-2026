@echo off
REM ================================================================
REM  ROBOT TRADER 2026 — AVVIO SCHEDULER DAEMON
REM  Avvia scheduler_daemon.py in background (finestra minimizzata)
REM  Configurare in Task Scheduler: eseguire all'accesso utente
REM ================================================================

setlocal

set BASE=C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS
set PYTHON="C:\Users\lucia\AppData\Local\Programs\Python\Python314\python.exe"

cd /d "%BASE%"

echo Avvio scheduler daemon...
start "RT2026 Scheduler" /MIN %PYTHON% scheduler_daemon.py

echo Scheduler avviato (finestra minimizzata).
endlocal
