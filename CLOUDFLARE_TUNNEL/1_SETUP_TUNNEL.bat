@echo off
chcp 65001 >nul
echo.
echo ================================================================
echo   ROBOT TRADER 2026 - SETUP CLOUDFLARE TUNNEL (passo 1/3)
echo ================================================================
echo.
echo Questo script esegue il login e crea il tunnel.
echo Si aprira' il browser per autenticarti su Cloudflare.
echo.
echo PREREQUISITO: cloudflared.exe deve essere in questa cartella
echo              oppure installato nel sistema.
echo.
pause

:: Controlla se cloudflared esiste nella cartella corrente o nel PATH
if exist "%~dp0cloudflared.exe" (
    set CLOUDFLARED="%~dp0cloudflared.exe"
) else (
    set CLOUDFLARED=cloudflared
)

echo.
echo [1/3] Login Cloudflare (si apre il browser)...
echo       Seleziona il dominio: www.fuerteventurecapital.com
echo.
%CLOUDFLARED% tunnel login

echo.
echo [2/3] Creazione tunnel "robot-trader"...
echo.
%CLOUDFLARED% tunnel create robot-trader

echo.
echo ================================================================
echo COPIA L'UUID mostrato sopra (es: a1b2c3d4-e5f6-...)
echo e incollalo nel file config_template.yml sostituendo
echo TUNNEL_UUID_QUI (due volte)
echo.
echo Poi esegui lo script: 2_CONFIGURA_DNS.bat
echo ================================================================
echo.
pause
