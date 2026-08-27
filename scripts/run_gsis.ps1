$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (Test-Path ".venv\python.exe") {
    & ".venv\python.exe" -m gsis_notifier --project-root $ProjectRoot
} elseif (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" -m gsis_notifier --project-root $ProjectRoot
} else {
    python -m gsis_notifier --project-root $ProjectRoot
}
