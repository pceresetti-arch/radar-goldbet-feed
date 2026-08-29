$ErrorActionPreference = 'Stop'

$Repo = 'https://raw.githubusercontent.com/pceresetti-arch/radar-goldbet-feed/main'
$Root = 'C:\BetFlagRadar'
$State = Join-Path $Root 'state'
$Script = Join-Path $Root 'betflag_true_open_close_watcher.py'
$Transport = Join-Path $Root 'betflag_session_transport.py'
$LoopScript = Join-Path $Root 'betflag_true_open_close_forever.ps1'

New-Item -ItemType Directory -Force -Path $Root,$State | Out-Null

# Keep the local collector in sync with the repository.
Invoke-WebRequest -UseBasicParsing "$Repo/collector/betflag_true_open_close_watcher.py" -OutFile $Script
Invoke-WebRequest -UseBasicParsing "$Repo/collector/betflag_session_transport.py" -OutFile $Transport

$Python = (Get-Command python.exe -ErrorAction Stop).Source

# The Python watcher intentionally works in short windows.  This resident
# wrapper restarts a new window every few seconds, so one Windows boot trigger
# is enough and there is no fragile minute-by-minute Task Scheduler trigger.
$Loop = @"
`$ErrorActionPreference = 'Continue'
while (`$true) {
    try {
        & '$Python' '$Script' --window-seconds 50 --interval 20
    }
    catch {
        Add-Content -Path '$Root\watcher-errors.log' -Value ((Get-Date -Format o) + ' ' + `$_.Exception.Message)
    }
    Start-Sleep -Seconds 10
}
"@
Set-Content -Path $LoopScript -Value $Loop -Encoding UTF8

$TaskName = 'BetFlag True Open Close Watcher'
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $LoopScript + '"')
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)

try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Resident BetFlag TRUE OPEN/CLOSE watcher. Starts automatically at Windows boot and continuously captures market birth/open, movements and the final pre-kickoff quote through the residential PC.' | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "INSTALLED: $TaskName"
Write-Host "AUTOSTART: Windows startup / SYSTEM"
Write-Host "STATE: $State\betflag-open-close-watch.json"
Write-Host "PYTHON: $Python"
Write-Host "WRAPPER: $LoopScript"
