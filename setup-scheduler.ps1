# -*- coding: utf-8 -*-
# Setup Windows Task Scheduler để chạy daily trading report 8am
# Chạy: powershell -ExecutionPolicy Bypass -File setup-scheduler.ps1

$TaskName = "DailyTradingReport"
$TaskFolder = "\Trading\"
$PythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$ScriptPath = "C:\Projects\Trading\report.py"
$ReportFolder = "C:\Projects\Trading\reports"
$LogFile = "$ReportFolder\report.log"

# Tạo folder reports nếu chưa có
if (-not (Test-Path $ReportFolder)) {
    New-Item -ItemType Directory -Path $ReportFolder -Force | Out-Null
    Write-Host "[OK] Created reports folder: $ReportFolder"
}

# PowerShell action: chạy report.py, append timestamp vào CSV
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "-u `"$ScriptPath`" --csv -o `"$ReportFolder\report_$(Get-Date -Format 'yyyy-MM-dd').csv`"" `
    -WorkingDirectory "C:\Projects\Trading"

# Trigger: daily 8:00 AM
$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At 08:00AM

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Register task
try {
    $TaskPath = "\" + $TaskFolder + $TaskName

    # Check if task already exists
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskFolder -ErrorAction SilentlyContinue
    if ($ExistingTask) {
        Write-Host "[WARN] Task '$TaskName' already exists. Updating..."
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskFolder -Confirm:$false
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskFolder `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host "[OK] Scheduled task created: $TaskName"
    Write-Host "     Trigger: Daily @ 8:00 AM"
    Write-Host "     Output: $ReportFolder\report_YYYY-MM-DD.csv"
    Write-Host ""
    Write-Host "[INFO] Task details:"
    Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskFolder | Select-Object TaskName, State | Format-Table -AutoSize

} catch {
    Write-Host "[ERROR] Failed to create scheduled task: $_"
    exit 1
}

Write-Host ""
Write-Host "=== Setup complete ==="
Write-Host "Next: Chạy manual test:"
Write-Host "  python report.py --csv -o C:\Projects\Trading\reports\test_report.csv"
