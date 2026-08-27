# ================================================================
# ROBOT TRADER 2026 — Reinstalla Task Scheduler (ESEGUIRE COME ADMIN)
# Trigger: ONLOGON + ONSTART (boot)
# Restart automatico se crasha: ogni 1 min, fino a 10 volte
# ================================================================

$taskName   = "RT2026 Scheduler Daemon"
$batPath    = "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS\START_SCHEDULER.bat"
$workingDir = "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"

# Rimuovi task esistente
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Trigger 1: all'accesso utente
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn

# Trigger 2: all'avvio del PC (delay 2 minuti per dare tempo a Windows)
$triggerBoot = New-ScheduledTaskTrigger -AtStartup
$triggerBoot.Delay = "PT2M"

# Azione: esegui il bat
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`"" -WorkingDirectory $workingDir

# Impostazioni: nessun timeout, restart su crash, non richiedere utente loggato
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable:$false `
    -StartWhenAvailable

# Registra il task con privilegi massimi
Register-ScheduledTask `
    -TaskName $taskName `
    -Trigger @($triggerLogon, $triggerBoot) `
    -Action $action `
    -Settings $settings `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "✓ Task '$taskName' installato correttamente."
Write-Host "  Trigger: accesso utente + avvio PC (delay 2 min)"
Write-Host "  Restart: automatico ogni 1 min se crasha (max 10 volte)"
Write-Host ""
Write-Host "Avvio immediato del task..."
Start-ScheduledTask -TaskName $taskName
Write-Host "✓ Scheduler avviato."
