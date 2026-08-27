@echo off
REM Lancia lo script PowerShell di sync fatture
PowerShell -ExecutionPolicy Bypass -File "%~dp0sync_fatture_vps.ps1"
