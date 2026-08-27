param(
    [string]$TaskName = "GSIS Latest Article Digest",
    [string]$Time = "08:00"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonCandidates = @(
    (Join-Path $ProjectRoot ".venv\python.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
)
$Python = $PythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    throw "Environment Python not found under .venv. Create the environment and install the project first."
}

$At = [datetime]::ParseExact($Time, "HH:mm", $null)
$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "-m gsis_notifier --project-root `"$ProjectRoot`"" `
    -WorkingDirectory $ProjectRoot
$Monday = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday -At $At
$Friday = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Friday -At $At
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($Monday, $Friday) `
    -Settings $Settings `
    -Description "Check new GSIS articles and send bilingual LinkedIn drafts to Feishu." `
    -Force

Write-Host "Scheduled task '$TaskName' installed for Monday and Friday at $Time."
Write-Host "Run it once now with: Start-ScheduledTask -TaskName '$TaskName'"
