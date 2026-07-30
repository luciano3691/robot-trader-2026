# Robot Trader 2026 — Task Scheduler Setup Script
# Esegui come Administrator!

# Variabili
$TaskName = "Robot Trader 2026 - Daily Screener"
$TaskPath = "\" 
$ScriptPath = "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS\robot_trader_scheduler_FIXED.bat"
$WorkingDirectory = "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"

# Orario TEST: 12:00 (puoi cambiare a 08:05 dopo il test)
$Time = "12:00:00"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Robot Trader 2026 - Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verifica che il file .bat esiste
if (-not (Test-Path $ScriptPath)) {
    Write-Host "❌ ERRORE: File .bat non trovato!" -ForegroundColor Red
    Write-Host "Percorso atteso: $ScriptPath" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ File .bat trovato: $ScriptPath" -ForegroundColor Green

# 2. Verifica se task esiste già
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "⚠️  Task già esiste. Eliminando..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Start-Sleep -Seconds 2
}

# 3. Crea trigger per 12:00, tutti i giorni
$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $Time

Write-Host "✅ Trigger creato: Ogni giorno alle $Time" -ForegroundColor Green

# 4. Crea azione (esegui .bat)
$Action = New-ScheduledTaskAction `
    -Execute $ScriptPath `
    -WorkingDirectory $WorkingDirectory

Write-Host "✅ Azione creata: Esegui $ScriptPath" -ForegroundColor Green

# 5. Crea settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

Write-Host "✅ Settings creati" -ForegroundColor Green

# 6. Crea principal (run with highest privileges)
$Principal = New-ScheduledTaskPrincipal `
    -UserID "NT AUTHORITY\SYSTEM" `
    -RunLevel Highest

Write-Host "✅ Principal creato (SYSTEM con highest privileges)" -ForegroundColor Green

# 7. Registra il task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -Principal $Principal `
        -Force | Out-Null
    
    Write-Host "✅ Task registrato con successo!" -ForegroundColor Green
} catch {
    Write-Host "❌ ERRORE durante la registrazione: $_" -ForegroundColor Red
    exit 1
}

# 8. Verifica che il task è stato creato
$VerifyTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($VerifyTask) {
    Write-Host "✅ Task verificato e confermato" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "CONFIGURAZIONE COMPLETATA" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📋 Dettagli Task:" -ForegroundColor Yellow
    Write-Host "  Nome: $TaskName"
    Write-Host "  Esecuzione: Ogni giorno alle $Time"
    Write-Host "  Script: $ScriptPath"
    Write-Host "  Working Dir: $WorkingDirectory"
    Write-Host ""
    Write-Host "🧪 TEST:" -ForegroundColor Yellow
    Write-Host "  Il task partirà automaticamente alle $Time"
    Write-Host "  Log salvato in: ROBOT TRADER 2026\PYTHON_SCRIPTS\..\LOGS\"
    Write-Host ""
    Write-Host "⚠️  PER CAMBIARE ORARIO A 08:05:" -ForegroundColor Yellow
    Write-Host "  1. Apri Task Scheduler"
    Write-Host "  2. Cerca '$TaskName'"
    Write-Host "  3. Modifica il trigger da $Time a 08:05:00"
    Write-Host ""
} else {
    Write-Host "❌ ERRORE: Task non è stato creato!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ SETUP COMPLETATO!" -ForegroundColor Green
Write-Host ""
