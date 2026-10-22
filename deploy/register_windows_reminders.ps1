# One-time: register Windows toast/popup reminders for COOL trial stop.
# Run elevated if Task Scheduler requires it: powershell -File deploy\register_windows_reminders.ps1

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stopScript = Join-Path $repo "deploy\stop_cool.ps1"

function Register-Reminder {
    param([string]$Name, [datetime]$When, [string]$Message)
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
        "-NoProfile -WindowStyle Normal -Command `"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('$Message','LookAgain COOL');`""
    $trigger = New-ScheduledTaskTrigger -Once -At $When
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Description "LookAgain COOL trial" | Out-Null
    Write-Host "Registered $Name at $When"
}

# Soft: finish benches/video
Register-Reminder -Name "LookAgain-COOL-Soft-2026-10-28" `
    -When ([datetime]"2026-10-28 09:00") `
    -Message "LookAgain: finish COOL demo video today. Hard stop tomorrow morning (stop_cool.ps1 + cancel Marketplace)."

# Hard: stop instance + cancel Marketplace
Register-Reminder -Name "LookAgain-COOL-Hard-2026-10-29" `
    -When ([datetime]"2026-10-29 08:00") `
    -Message "LookAgain HARD STOP: run deploy\stop_cool.ps1 then cancel COOL in AWS Marketplace Manage subscriptions. Trial converts to paid today."

Write-Host "Done. Stop script path: $stopScript"
