@echo off
chcp 65001 >nul
echo.
echo ================================================================
echo   ROBOT TRADER 2026 - CONFIGURA DNS (passo 2/3)
echo ================================================================
echo.
echo Questo script aggiunge il record CNAME su Cloudflare DNS.
echo.

if exist "%~dp0cloudflared.exe" (
    set CLOUDFLARED="%~dp0cloudflared.exe"
) else (
    set CLOUDFLARED=cloudflared
)

echo Configurazione DNS: www.fuerteventurecapital.com
echo.
%CLOUDFLARED% tunnel route dns robot-trader www.fuerteventurecapital.com

echo.
echo ================================================================
echo Se il comando e' andato a buon fine, ora:
echo.
echo 1. Apri config_template.yml
echo 2. Sostituisci TUNNEL_UUID_QUI con il tuo UUID (due volte)
echo 3. Salvalo in: C:\Users\lucia\.cloudflared\config.yml
echo.
echo Poi esegui: 3_AVVIA_TUNNEL.bat
echo ================================================================
echo.
pause
