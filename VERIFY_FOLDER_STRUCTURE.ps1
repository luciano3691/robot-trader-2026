
# VERIFY_FOLDER_STRUCTURE.ps1
# Questo script verifica se tutti i file sono nelle cartelle giuste

# Set the base path
$basePath = "C:\Users\lucia\Desktop\Robot Trader 2026"

# Define the expected structure
$expectedStructure = @{
    "01_DOCUMENTAZIONE_OPERATIVA" = @(
        "1A_PROCEDURA_SCREENER_COMPLETA.docx",
        "1B_ROADMAP_FONDI_GANTT_CHART.xlsx",
        "1C_BACKUP_DISASTER_RECOVERY_PLAN.docx"
    )
    "02_SETUP_INFRASTRUTTURA" = @(
        "2A_SETUP_INFRASTRUTTURA_CHECKLIST.docx",
        "2B_EMAIL_CONFIG_TEST_REPORT.xlsx"
    )
    "03_MARKETING_LANDING_PAGES" = @(
        "3A_LANDING_PAGE_AZIONI_FINAL.html",
        "3A_LANDING_PAGE_FONDI_FINAL.html",
        "3A_LANDING_PAGE_ETF_FINAL.html",
        "3B_EMAIL_SEQUENCE_FONDI.docx"
    )
    "04_GITHUB_PROJECT_BOARD" = @(
        "4_GITHUB_PROJECT_BOARD_REVIEW.xlsx",
        "4_GITHUB_PROJECT_BOARD_STRATEGY.docx"
    )
    "05_LINKEDIN_AUTOMATION" = @(
        "5A_N8N_LINKEDIN_AUTOMATION_GUIDE.txt",
        "5B_CONTENT_CALENDAR_MAGGIO_2026.xlsx",
        "5C_LINKEDIN_POST_TEMPLATES.txt",
        "5D_N8N_IMPLEMENTATION_GUIDE.txt"
    )
    "06_EMAIL_LANDING_OPTIMIZATION" = @(
        "6A_MAILCHIMP_SETUP_GUIDE.txt",
        "6B_LANDING_PAGE_AB_TEST_PLAN.xlsx",
        "6C_SEO_OPTIMIZATION_GUIDE.txt"
    )
    "07_CUSTOMER_ONBOARDING_SUPPORT" = @(
        "7A_CUSTOMER_ONBOARDING_FLOW.txt",
        "7B_SUPPORT_TICKETING_SYSTEM.xlsx",
        "7C_CUSTOMER_SUCCESS_PLAYBOOK.txt",
        "7D_REFUND_CANCELLATION_POLICY.txt"
    )
    "08_EMAIL_RECIPIENTS_SYSTEM" = @(
        "DATABASE_RECIPIENTS_STRUCTURE.json",
        "DATABASE_RECIPIENTS.json",
        "ADMIN_DASHBOARD_EMAIL_RECIPIENTS.html",
        "scheduler_daemon_UPDATED.py",
        "manage_recipients_CLI.py",
        "DYNAMIC_RECIPIENTS_IMPLEMENTATION_GUIDE.txt"
    )
    "PYTHON_SCRIPTS" = @(
        "value_screener.py",
        "email_notifier.py",
        "scheduler_daemon.py"
    )
    "REPORTS_DAILY" = @()
}

# Color definitions
$green = "Green"
$red = "Red"
$yellow = "Yellow"

# Check if base path exists
if (-not (Test-Path $basePath)) {
    Write-Host "ERROR: Base path does not exist: $basePath" -ForegroundColor $red
    exit 1
}

Write-Host "=" * 70
Write-Host "ROBOT TRADER 2026 — FOLDER STRUCTURE VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 70
Write-Host ""

$totalFolders = 0
$correctFolders = 0
$totalFiles = 0
$correctFiles = 0
$missingFiles = @()

# Check each folder and its files
foreach ($folder in $expectedStructure.Keys) {
    $folderPath = Join-Path $basePath $folder
    $totalFolders++
    
    if (Test-Path $folderPath) {
        Write-Host "✅ FOLDER: $folder" -ForegroundColor $green
        $correctFolders++
        
        # Check files in this folder
        foreach ($file in $expectedStructure[$folder]) {
            $filePath = Join-Path $folderPath $file
            $totalFiles++
            
            if (Test-Path $filePath) {
                Write-Host "   ✅ FILE: $file" -ForegroundColor $green
                $correctFiles++
            } else {
                Write-Host "   ❌ MISSING: $file" -ForegroundColor $red
                $missingFiles += "$folder\$file"
            }
        }
    } else {
        Write-Host "❌ FOLDER: $folder (NOT FOUND)" -ForegroundColor $red
        
        # Count missing files
        foreach ($file in $expectedStructure[$folder]) {
            $missingFiles += "$folder\$file"
        }
        $totalFiles += $expectedStructure[$folder].Count
    }
    
    Write-Host ""
}

# Summary Report
Write-Host "=" * 70
Write-Host "SUMMARY REPORT" -ForegroundColor Cyan
Write-Host "=" * 70
Write-Host ""
Write-Host "Folders: $correctFolders / $totalFolders" -ForegroundColor $(if ($correctFolders -eq $totalFolders) { $green } else { $red })
Write-Host "Files:   $correctFiles / $totalFiles" -ForegroundColor $(if ($correctFiles -eq $totalFiles) { $green } else { $red })
Write-Host ""

if ($correctFiles -eq $totalFiles) {
    Write-Host "✅ ALL FILES IN CORRECT LOCATION!" -ForegroundColor $green
    Write-Host ""
    Write-Host "You're ready for tonight's deployment! 🚀" -ForegroundColor $green
} else {
    Write-Host "❌ MISSING FILES DETECTED" -ForegroundColor $red
    Write-Host ""
    Write-Host "Please copy these files:" -ForegroundColor $yellow
    foreach ($missing in $missingFiles) {
        Write-Host "   • $missing" -ForegroundColor $yellow
    }
    Write-Host ""
    Write-Host "Use File Explorer to move files to correct folders" -ForegroundColor $yellow
}

Write-Host ""
Write-Host "=" * 70
