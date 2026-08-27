# WATCHDOG - Robot Trader 2026 Scheduler
# Controlla ogni volta che viene eseguito se scheduler_daemon.py e' vivo.
# Se non gira, lo riavvia tramite START_SCHEDULER.bat.

$BASE = "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"
$LOG  = "$BASE\watchdog.log"
$BAT  = "$BASE\START_SCHEDULER.bat"
$TS   = (Get-Date -Format "dd/MM/yyyy HH:mm:ss")

$proc = Get-WmiObject Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*scheduler_daemon*' }

if ($proc) {
    Add-Content -Path $LOG -Value "[$TS] OK - scheduler_daemon in esecuzione (PID $($proc.ProcessId))"
} else {
    Add-Content -Path $LOG -Value "[$TS] WARN - scheduler_daemon NON trovato -> riavvio"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$BAT`"" -WindowStyle Minimized
    Add-Content -Path $LOG -Value "[$TS] INFO - START_SCHEDULER.bat lanciato"
}
