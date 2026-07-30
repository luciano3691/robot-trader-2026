@echo off
REM ROBOT TRADER 2026 - SCHEDULER NOTTURNO
REM Esecuzione: 23:05 Canarie
REM Durata: ~4 ore (screener) + email automatiche
REM Orchestrator coordina: AZIONI → ETF → FONDI → FONDI_EU → EMAIL

setlocal

set BASE=C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS
set PYTHON="C:\Users\lucia\AppData\Local\Programs\Python\Python314\python.exe"
set LOGS=%BASE%\logs

if not exist "%LOGS%" mkdir "%LOGS%"

REM Nome log datato (YYYYMMDD_HHMM)
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set _D=%%c%%b%%a
for /f "tokens=1-2 delims=: " %%a in ("%time: =0%") do set _T=%%a%%b
set LOGFILE=%LOGS%\robot_trader_%_D%_%_T%.log

echo ======================================== >> "%LOGFILE%"
echo ROBOT TRADER 2026 - ESECUZIONE NOTTURNA >> "%LOGFILE%"
echo Avvio: %date% %time%                    >> "%LOGFILE%"
echo ======================================== >> "%LOGFILE%"

cd /d "%BASE%"

echo Avvio ORCHESTRATOR... >> "%LOGFILE%"
%PYTHON% orchestrator.py >> "%LOGFILE%" 2>&1

set RC=%errorlevel%

if %RC% neq 0 (
    echo. >> "%LOGFILE%"
    echo ERRORE orchestrator - codice: %RC% >> "%LOGFILE%"
    echo ERRORE durante esecuzione orchestrator (codice %RC%) >&2
    exit /b %RC%
)

echo. >> "%LOGFILE%"
echo ======================================== >> "%LOGFILE%"
echo COMPLETATO: %date% %time%               >> "%LOGFILE%"
echo Report in REPORTS_DAILY\               >> "%LOGFILE%"
echo ======================================== >> "%LOGFILE%"

endlocal
