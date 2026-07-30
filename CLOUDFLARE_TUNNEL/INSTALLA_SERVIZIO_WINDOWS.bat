@echo off
chcp 65001 >nul
echo.
echo ================================================================
echo   INSTALLA CLOUDFLARE TUNNEL COME SERVIZIO WINDOWS
echo   (si avvia automaticamente all'accensione del PC)
echo ================================================================
echo.
echo ATTENZIONE: richiede diritti di amministratore.
echo Esegui questo file con "Esegui come amministratore".
echo.
pause

if exist "%~dp0cloudflared.exe" (
    set CLOUDFLARED="%~dp0cloudflared.exe"
) else (
    set CLOUDFLARED=cloudflared
)

echo Installazione servizio Windows...
%CLOUDFLARED% service install

echo.
echo Avvio servizio...
net start cloudflared

echo.
echo ================================================================
echo SERVIZIO INSTALLATO.
echo Il tunnel si avviera' automaticamente ad ogni accensione del PC.
echo.
echo Per verificare: Apri Gestione Servizi (services.msc)
echo                 Cerca "Cloudflare Tunnel"
echo.
echo Per disinstallare: cloudflared service uninstall
echo ================================================================
echo.
pause
