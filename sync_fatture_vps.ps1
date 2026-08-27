# ═══════════════════════════════════════════════════════════
#  SYNC FATTURE VPS → Desktop\Robot Trader 2026\FATTURE\
#  Scarica dal VPS solo i PDF che non esistono già in locale
#  Programmato ogni ora da Task Scheduler Windows
# ═══════════════════════════════════════════════════════════

$SSH_KEY  = "$env:USERPROFILE\.ssh\vps_hetzner"
$VPS      = "root@178.104.93.65"
$DEST     = "$PSScriptRoot\FATTURE"
$LOG      = "$PSScriptRoot\sync_fatture.log"

# Crea cartella locale se non esiste
if (-not (Test-Path $DEST)) { New-Item -ItemType Directory -Path $DEST | Out-Null }

# Ottieni lista PDF sul VPS via SSH
$lista_vps = ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o BatchMode=yes $VPS `
    "ls /root/FATTURE/*.pdf 2>/dev/null | xargs -I{} basename {}" 2>$null

if (-not $lista_vps) {
    Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') - Nessun PDF sul VPS o connessione fallita"
    exit 0
}

$scaricati = 0
foreach ($file in $lista_vps) {
    $file = $file.Trim()
    if (-not $file) { continue }
    $dest_file = Join-Path $DEST $file
    if (-not (Test-Path $dest_file)) {
        scp -i $SSH_KEY -o StrictHostKeyChecking=no -o BatchMode=yes `
            "${VPS}:/root/FATTURE/${file}" $dest_file 2>$null
        if ($?) {
            Write-Host "[OK] Scaricata: $file"
            $scaricati++
        }
    }
}

$msg = "$(Get-Date -Format 'yyyy-MM-dd HH:mm') - Sync OK: $scaricati nuovi PDF scaricati"
Add-Content $LOG $msg
Write-Host $msg
