@echo off
chcp 65001 >nul
echo.
echo ================================================================
echo   ROBOT TRADER 2026 - AVVIO TUNNEL (passo 3/3)
echo ================================================================
echo.

if exist "%~dp0cloudflared.exe" (
    set CLOUDFLARED="%~dp0cloudflared.exe"
) else (
    set CLOUDFLARED=cloudflared
)

echo Avvio tunnel Cloudflare...
echo URL pubblico: https://www.fuerteventurecapital.com
echo.
echo NON chiudere questa finestra!
echo.
%CLOUDFLARED% tunnel run robot-trader
