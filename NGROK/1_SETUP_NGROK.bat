@echo off
chcp 65001 >nul
echo.
echo ================================================================
echo   ROBOT TRADER 2026 - SETUP NGROK (una tantum)
echo ================================================================
echo.
echo PREREQUISITI:
echo   1. Crea account su https://dashboard.ngrok.com
echo   2. Copia il tuo Authtoken da: Dashboard ^> Getting Started ^> Your Authtoken
echo   3. Crea dominio statico:       Dashboard ^> Cloud Edge ^> Domains ^> + New Domain
echo   4. Metti ngrok.exe in questa cartella (NGROK\)
echo.
echo ================================================================
echo.

:: Controlla ngrok.exe
if not exist "%~dp0ngrok.exe" (
    echo ERRORE: ngrok.exe non trovato in questa cartella.
    echo Scaricalo da: https://ngrok.com/download  (Windows AMD64)
    echo e mettilo qui: %~dp0ngrok.exe
    pause
    exit /b 1
)

:: Legge authtoken dal file di config (se esiste)
if exist "%~dp0ngrok_authtoken.txt" (
    set /p AUTHTOKEN=<"%~dp0ngrok_authtoken.txt"
) else (
    echo Incolla il tuo Authtoken ngrok e premi INVIO:
    set /p AUTHTOKEN=
)

echo.
echo Configurazione authtoken...
"%~dp0ngrok.exe" config add-authtoken %AUTHTOKEN%

echo.
echo ================================================================
echo SETUP COMPLETATO
echo Ora esegui START_SISTEMA_PUBBLICO.bat per avviare tutto.
echo ================================================================
echo.
pause
