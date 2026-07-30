@echo off
REM ================================================================
REM  ROBOT TRADER 2026 — INSTALLA TASK SCHEDULER
REM  Eseguire come AMMINISTRATORE (tasto destro → Esegui come amministratore)
REM ================================================================

schtasks /create ^
  /tn "RT2026 Scheduler Daemon" ^
  /tr "\"C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS\START_SCHEDULER.bat\"" ^
  /sc ONLOGON ^
  /rl HIGHEST ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo ✓ Task creato con successo.
    echo   Nome: RT2026 Scheduler Daemon
    echo   Trigger: Ad ogni accesso utente
    echo   Avvio: START_SCHEDULER.bat
) else (
    echo.
    echo ✗ Errore creazione task. Eseguire come Amministratore.
)

pause
