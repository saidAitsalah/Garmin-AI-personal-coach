# Registers a daily Windows scheduled task that runs the morning job.
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 [-Time 06:30] [-Until 10:00]
#
# The job starts at -Time, then checks Garmin every 10 minutes until last night's sleep has synced
# (or until -Until), builds the report and sends it. If the PC was off at -Time, it runs as soon as
# the PC is on (StartWhenAvailable). Remove it with: Unregister-ScheduledTask -TaskName CoachSanteIA
param(
    [string]$Time = "06:30",
    [string]$Until = "10:00"
)

$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root ".venv\Scripts\coach.exe"
if (-not (Test-Path $exe)) { throw "Not found: $exe. Create the venv and run 'pip install -e .' first." }

$action = New-ScheduledTaskAction -Execute $exe -Argument "run --wait-for-sleep --until $Until" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Register-ScheduledTask -TaskName "CoachSanteIA" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Daily AI health coach report (Garmin -> Gemini -> Telegram)" -Force
Write-Host "Task 'CoachSanteIA' registered for $Time daily. Logs: data\logs\coach.log"
