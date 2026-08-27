@echo off
REM Installa il Task Scheduler per sync fatture ogni ora
REM Eseguire UNA SOLA VOLTA come Amministratore

set SCRIPT="%USERPROFILE%\Desktop\Robot Trader 2026\sync_fatture_vps.ps1"
set TASKNAME="SyncFattureRT2026"

REM Elimina task se già esiste
schtasks /delete /tn %TASKNAME% /f >nul 2>&1

REM Crea task: ogni ora, parte subito al login
schtasks /create ^
  /tn %TASKNAME% ^
  /tr "PowerShell -ExecutionPolicy Bypass -WindowStyle Hidden -File %SCRIPT%" ^
  /sc HOURLY ^
  /mo 1 ^
  /st 00:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

echo.
echo ✅ Task Scheduler installato: sync fatture ogni ora
echo    Nome task: %TASKNAME%
echo    Per avviare subito: schtasks /run /tn %TASKNAME%
echo.
pause
